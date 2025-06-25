import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "secret-key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static/uploads"

db = SQLAlchemy(app)

# --- Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)
    profile_pic = db.Column(db.String(200), default="")
    is_admin = db.Column(db.Boolean, default=False)
    balance = db.Column(db.Float, default=1000.0)
    orders = db.relationship('Order', backref='user', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    images = db.relationship('ProductImage', backref='product', cascade="all, delete", lazy=True)

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(200))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    size = db.Column(db.String(10))
    color = db.Column(db.String(20))
    quantity = db.Column(db.Integer)
    product = db.relationship('Product')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    items = db.Column(db.Text)
    total = db.Column(db.Float)
    shipping_name = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    street = db.Column(db.String(200))
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    postal_code = db.Column(db.String(30))

# --- Helper functions ---

def current_user():
    if "user_id" in session:
        return User.query.get(session["user_id"])
    return None

def save_file(file):
    if file and file.filename != '':
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return f"uploads/{filename}"
    return None

# --- Routes ---

@app.route("/")
def home():
    user = current_user()
    products = Product.query.all()
    return render_template("home.html", products=products, user=user)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        age = request.form["age"]
        role = request.form.get("role", "User")
        is_admin = True if role == "Admin" else False

        existing = User.query.filter_by(username=username).first()
        if existing:
            flash("Username already taken!", "danger")
            return redirect(url_for("register"))

        profile_pic = ""
        pic = request.files.get("profile_pic")
        if pic and pic.filename != "":
            filename = save_file(pic)
            profile_pic = filename if filename else ""

        user = User(username=username, password=password, age=int(age),
                    profile_pic=profile_pic, is_admin=is_admin, balance=1000.0)
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        flash("Registered successfully!", "success")
        return redirect(url_for("home"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session["user_id"] = user.id
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("home"))

@app.route("/profile")
def profile():
    user = current_user()
    if not user:
        flash("Please login first", "warning")
        return redirect(url_for("login"))
    return render_template("profile.html", user=user)

@app.route("/wallet", methods=["GET", "POST"])
def wallet():
    user = current_user()
    if not user:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        amount = request.form.get("amount")
        try:
            amount = float(amount)
            if amount <= 0:
                flash("Enter a valid amount", "danger")
                return redirect(url_for("wallet"))
        except:
            flash("Enter a valid number", "danger")
            return redirect(url_for("wallet"))

        if not all([request.form.get("name_on_card"),
                    request.form.get("card_number"),
                    request.form.get("expiry_date"),
                    request.form.get("cvv")]):
            flash("Fill all card details", "danger")
            return redirect(url_for("wallet"))

        user.balance += amount
        db.session.commit()
        flash(f"Added ${amount:.2f} to your balance!", "success")
        return redirect(url_for("wallet"))

    return render_template("wallet.html", user=user)

@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    user = current_user()
    if not user or not user.is_admin:
        flash("Admin only", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        price = float(request.form["price"])
        description = request.form.get("description", "")
        product = Product(name=name, price=price, description=description)
        db.session.add(product)
        db.session.commit()

        files = request.files.getlist("images")
        for f in files:
            filename = save_file(f)
            if filename:
                img = ProductImage(image_url=filename, product_id=product.id)
                db.session.add(img)
        db.session.commit()
        flash("Product added", "success")
        return redirect(url_for("home"))

    return render_template("add_product.html", user=user)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    user = current_user()
    product = Product.query.get_or_404(product_id)
    return render_template("product_detail.html", product=product, user=user)

@app.route("/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    user = current_user()
    if not user or not user.is_admin:
        flash("Admin only area", "danger")
        return redirect(url_for("login"))

    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        product.name = request.form["name"]
        product.price = float(request.form["price"])
        product.description = request.form.get("description", "")

        files = request.files.getlist("images")
        for f in files:
            filename = save_file(f)
            if filename:
                img = ProductImage(image_url=filename, product_id=product.id)
                db.session.add(img)

        db.session.commit()
        flash("Product updated", "success")
        return redirect(url_for("product_detail", product_id=product.id))

    return render_template("edit_product.html", product=product, user=user)

@app.route("/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    user = current_user()
    if not user or not user.is_admin:
        flash("Admin only area", "danger")
        return redirect(url_for("login"))

    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted", "success")
    return redirect(url_for("home"))

@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    user = current_user()
    if not user:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    product = Product.query.get_or_404(product_id)
    size = request.form.get("size")
    color = request.form.get("color")
    try:
        quantity = int(request.form.get("quantity"))
    except:
        quantity = 1

    if not size or not color or quantity < 1:
        flash("Choose size, color and quantity", "danger")
        return redirect(url_for("product_detail", product_id=product.id))

    existing = CartItem.query.filter_by(user_id=user.id, product_id=product.id, size=size, color=color).first()
    if existing:
        existing.quantity += quantity
    else:
        item = CartItem(user_id=user.id, product_id=product.id, size=size, color=color, quantity=quantity)
        db.session.add(item)

    db.session.commit()
    flash("Added to cart", "success")
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    user = current_user()
    if not user:
        flash("Please login first", "danger")
        return redirect(url_for("login"))
    cart_items = CartItem.query.filter_by(user_id=user.id).all()
    subtotal = sum(item.product.price * item.quantity for item in cart_items)
    tax = subtotal * 0.1
    shipping = 10 if cart_items else 0
    total = subtotal + tax + shipping
    return render_template("cart.html", cart=cart_items, user=user,
                           subtotal=subtotal, tax=tax, shipping=shipping, total=total)

@app.route("/remove_item/<int:item_id>", methods=["POST"])
def remove_item(item_id):
    user = current_user()
    if not user:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    item = CartItem.query.get_or_404(item_id)
    if item.user_id != user.id:
        flash("Not authorized", "danger")
        return redirect(url_for("cart"))

    db.session.delete(item)
    db.session.commit()
    flash("Item removed", "success")
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["POST"])
def checkout():
    user = current_user()
    if not user:
        flash("Please login first", "danger")
        return redirect(url_for("login"))

    cart_items = CartItem.query.filter_by(user_id=user.id).all()
    if not cart_items:
        flash("Cart is empty", "warning")
        return redirect(url_for("cart"))

    subtotal = sum(item.product.price * item.quantity for item in cart_items)
    tax = subtotal * 0.1
    shipping = 10
    total = subtotal + tax + shipping

    if user.balance < total:
        flash("Not enough balance! Please add money to your wallet.", "danger")
        return redirect(url_for("wallet"))

    shipping_name = request.form.get("shipping_name")
    phone = request.form.get("phone")
    street = request.form.get("street")
    city = request.form.get("city")
    country = request.form.get("country")
    postal_code = request.form.get("postal_code")

    if not all([shipping_name, phone, street, city, country, postal_code]):
        flash("Fill all shipping info", "danger")
        return redirect(url_for("cart"))

    items_summary = "; ".join([f"{item.product.name} (x{item.quantity})" for item in cart_items])
    order = Order(user_id=user.id, items=items_summary, total=total,
                  shipping_name=shipping_name, phone=phone, street=street,
                  city=city, country=country, postal_code=postal_code)

    db.session.add(order)
    user.balance -= total
    CartItem.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    flash("Order placed successfully!", "success")
    return render_template("checkout_done.html", user=user)


if __name__ == "__main__":
    if not os.path.exists("shop.db"):
        with app.app_context():
            db.create_all()
        print("Database created!")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.run(debug=True)
