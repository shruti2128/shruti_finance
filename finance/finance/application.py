import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    tot = 0
    user_id = session["user_id"]
    tran = db.execute("SELECT symbol,name, sum(shares), price, sum(shares*price) FROM transactions WHERE u_id = ? GROUP BY name", user_id)
    l = len(tran)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
    for i in range(l):
        tot += tran[i]["sum(shares*price)"]
    return render_template("index.html", tran=tran, cash=cash, l=l, usd=usd, tot=tot)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)
        if not stock or not symbol:
            return apology("SYMBOL INCORRECT")
        try: 
            shares = int(request.form.get("shares"))
        except:
            return apology("ENTER VALID NUMBER OF SHARES", 400)
        if shares <= 0:
            return apology("ENTER VALID NUMBER OF SHARES", 400)
       
        user_id = session["user_id"]
        cash = db.execute("SELECT cash FROM USERS WHERE id = ?", user_id)
        cash = cash[0]["cash"] 
        print(cash)
        name = stock["name"]
        price = stock["price"]
        tot = price*shares
        if cash < tot:
            return apology("NOT ENOUGH CASH IN HAND")
        else:
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - tot, user_id)
            db.execute("INSERT INTO transactions (u_id,name,shares,price,type,symbol) VALUES(?,?,?,?,?,?)",
                       user_id, name, shares, price, "buy", symbol)
        return redirect("/")
    else:
        return render_template("buy.html")
   

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    hist = db.execute("SELECT u_id,name,shares,price,type,symbol,time FROM transactions WHERE u_id = ?", user_id)
    return render_template("history.html", hist=hist, usd=usd)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)
        if not symbol:
            return apology("Symbol incorrect")
        if not stock:
            return apology("Symbol not found")
        return render_template("quoted.html", stock=stock, usdf=usd)
        
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        password = request.form.get("password")
        username = request.form.get("username")
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation password", 400)
        if request.form.get("confirmation") != request.form.get("password"):
            return apology("Confirmation password incorrect", 400)
        h = generate_password_hash(password)
        try: 
            db.execute("INSERT INTO users (username,hash) VALUES(?,?)", username, h)
            return redirect("/")
        except:
            return apology("username already exits")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        price = lookup(symbol)["price"]
        name = lookup(symbol)["name"]
        tran = db.execute("SELECT symbol,sum(shares) FROM transactions WHERE u_id = ? GROUP BY symbol", user_id)
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        s = []
        for i in tran:
            s.append(i["symbol"])
        if not symbol:
            return apology("INCORRECT SYMBOL")
        if symbol not in s:
            return apology("STOCK NOT BOUGHT")
        if not shares or shares <= 0:
            return aplogy("INVALID SHARES")
        for i in tran:
            if symbol == i["symbol"]:
                if shares > i["sum(shares)"]:
                    return apology("NOT ENOUGH SHARES BOUGHT TO SELL")
                if shares < i["sum(shares)"]:
                    db.execute("INSERT INTO transactions (u_id,name,shares,price,type,symbol) VALUES(?,?,?,?,?,?)",
                               user_id, name, -shares, price, "sell", symbol)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash + (shares*price), user_id)
        return redirect("/")
    else:
        symbols = db.execute("SELECT symbol,sum(shares) FROM transactions WHERE u_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", symbols=symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
