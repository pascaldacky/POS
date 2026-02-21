import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime
import qrcode

app = Flask(__name__)
app.secret_key = "tra-pos-secret"

# ---------- DATABASE ----------
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///shop.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ---------- EMAIL ----------
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "pchahama1103@gmail.com"
app.config["MAIL_PASSWORD"] = "gjekbbqhxlckghpz"
app.config["MAIL_DEFAULT_SENDER"] = "pchahama1103@gmail.com"

mail = Mail(app)

# ---------- QR CODES ----------
QR_FOLDER = "static/qrcodes"
os.makedirs(QR_FOLDER, exist_ok=True)

# ---------- MODELS ----------
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Float)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("SaleItem", backref="sale", cascade="all, delete")

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    qty = db.Column(db.Integer)
    product = db.relationship("Product")

# ---------- ROUTES ----------
@app.route("/")
def index():
    products = Product.query.all()
    return render_template("index.html", products=products)

@app.route("/add_product", methods=["POST"])
def add_product():
    name = request.form["name"]
    price = float(request.form["price"])
    db.session.add(Product(name=name, price=price))
    db.session.commit()
    flash(f"Product {name} added")
    return redirect(url_for("index"))

# ---------- CART ----------
@app.route("/cart/add/<int:id>")
def add_to_cart(id):
    product = Product.query.get_or_404(id)
    cart = session.get("cart", {})
    cart[str(id)] = cart.get(str(id), 0) + 1
    session["cart"] = cart
    flash(f"Product '{product.name}' Added to A shopping cart", "success")
    return redirect(url_for("index"))

@app.route("/cart")
def cart():
    items, total = [], 0
    for pid, qty in session.get("cart", {}).items():
        p = Product.query.get(int(pid))
        subtotal = p.price * qty
        total += subtotal
        items.append({"p": p, "qty": qty, "subtotal": subtotal})
    return render_template("cart.html", items=items, total=total)

@app.route("/cart/increase/<int:id>")
def increase_qty(id):
    cart = session.get("cart", {})
    if str(id) in cart:
        cart[str(id)] += 1
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/cart/decrease/<int:id>")
def decrease_qty(id):
    cart = session.get("cart", {})
    if str(id) in cart:
        cart[str(id)] -= 1
        if cart[str(id)] <= 0:
            cart.pop(str(id))
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/cart/remove/<int:id>")
def remove_item(id):
    cart = session.get("cart", {})
    cart.pop(str(id), None)
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/cart/clear")
def clear_cart():
    session.pop("cart", None)
    flash("Cart cleared")
    return redirect(url_for("index"))

# ---------- CHECKOUT ----------
@app.route("/checkout")
def checkout():
    cart = session.get("cart")
    if not cart:
        flash("Cart empty")
        return redirect(url_for("index"))

    sale = Sale()
    db.session.add(sale)
    db.session.commit()

    total = 0
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        db.session.add(SaleItem(sale_id=sale.id, product_id=p.id, qty=qty))
        total += p.price * qty

    db.session.commit()
    session.pop("cart")

    qr_data = f"TRA RECEIPT\nSALE:{sale.id}\nTOTAL:{total}"
    qr_path = f"{QR_FOLDER}/sale_{sale.id}.png"
    qrcode.make(qr_data).save(qr_path)

    return redirect(url_for("receipt", sale_id=sale.id))

@app.route("/product/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):
   product = Product.query.get_or_404(product_id)
   db.session.delete(product)
   db.session.commit()
   flash(f"Product '{product_id}' has been deleted.", "success")
   return redirect(url_for("index"))

# ---------- RECEIPT ----------
@app.route("/receipt/<int:sale_id>", methods=["GET","POST"])
def receipt(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    total = sum(i.product.price*i.qty for i in sale.items)
    vat = total * 0.18
    grand = total + vat
    qr_file = f"sale_{sale.id}.png"

    if request.method == "POST":
        email = request.form["email"]

        mail.init_app(app)

        try:
            msg = Message(
                subject=f"DEFAULTS EMAILS #{sale.id}",
                recipients=[email],
                html=render_template("receipt_email.html", sale=sale, total=total, vat=vat, grand=grand, qr_image=qr_file)
            )
            mail.send(msg)
            flash(f"Receipt sent to [{email}] successfully")
        except Exception as e:
            flash(f"Email failed. Use Gmail App Password.{str(e)}")

    return render_template("receipt.html", sale=sale, total=total, vat=vat, grand=grand, qr_file=qr_file)

# ---------- RUN ----------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

