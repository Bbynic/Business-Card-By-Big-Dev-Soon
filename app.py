import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


# New route for the home page (portfolio)
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    returnresponse

# New route for the home page (portfolio)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Get form data
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validate form data
        if not username or not password or not confirmation:
            return apology("Please provide username, password, and confirmation")

        if password != confirmation:
            return apology("Passwords do not match")

        # Check if username already exists
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) > 0:
            return apology("Username already exists")

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Insert the new user into the database
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                   username, hashed_password)

        # Log in the user
        user_id = db.execute(
            "SELECT id FROM users WHERE username = ?", username)[0]["id"]
        session["user_id"] = user_id

        # Redirect to the home page
        return redirect("/")

    else:
        # If the request is a GET, render the registration form
        return render_template("register.html")


# New route for the home page (portfolio)
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # Get the stock symbol from the form data
        symbol = request.form.get("symbol")

        # Validate form data
        if not symbol:
            return apology("Please enter a stock symbol")

        # Look up the stock information
        stock_info = lookup(symbol)

        if not stock_info:
            return apology("Invalid stock symbol")

        # Render the stock information
        return render_template("quoted.html", stock=stock_info)

    else:
        # If the request is a GET, render the quote form
        return render_template("quote.html")


# New route for the home page (portfolio)
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # Get form data
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Validate form data
        if not symbol or not shares:
            return apology("Please provide both symbol and shares")

        # Ensure shares is a positive integer
        try:
            shares = int(shares)
            if shares <= 0:
                raise ValueError("Shares must be a positive integer")
        except ValueError:
            return apology("Shares must be a positive integer")

        # Look up the current stock price
        quote = lookup(symbol)
        if not quote:
            return apology("Invalid symbol")

        # Calculate the total cost of the shares
        total_cost = quote["price"] * shares

        # Check if the user has enough cash
        user_id = session["user_id"]
        user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
        if user["cash"] < total_cost:
            return apology("Not enough cash to buy")

        # Insert the transaction into the database
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, total, transaction_type) VALUES (?, ?, ?, ?, ?, ?)",
                   user_id, quote["symbol"], shares, quote["price"], total_cost, "buy")

        # Update user's cash
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?",
                   total_cost, user_id)

        # Redirect to the home page
        return redirect("/")

    else:
        # If the request is a GET, render the buy form
        return render_template("buy.html")


# New route for the home page (portfolio)
@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get user's id
    user_id = session["user_id"]

    # Query the user's cash
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    cash = user["cash"]

    # Query the user's portfolio
    portfolio = db.execute(
        "SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0",
        user_id
    )

    # Add real-time stock data to the portfolio
    total_portfolio_value = cash
    for stock in portfolio:
        quote = lookup(stock["symbol"])
        stock["name"] = quote["name"]
        stock["price"] = quote["price"]
        stock["total_value"] = quote["price"] * stock["total_shares"]
        total_portfolio_value += stock["total_value"]

    return render_template("index.html", cash=cash, portfolio=portfolio, total_portfolio_value=total_portfolio_value)


# New route for the home page (portfolio)
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # Get form data
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Validate form data
        if not symbol or not shares:
            return apology("Please provide both symbol and shares")

        # Ensure shares is a positive integer
        try:
            shares = int(shares)
            if shares <= 0:
                raise ValueError("Shares must be a positive integer")
        except ValueError:
            return apology("Shares must be a positive integer")

        # Check if the user owns enough shares of the stock
        user_id = session["user_id"]
        owned_shares = db.execute(
            "SELECT SUM(shares) as total_shares FROM transactions WHERE user_id = ? AND symbol = ?", user_id, symbol)[0]["total_shares"]
        if not owned_shares or owned_shares < shares:
            return apology("Not enough shares to sell")

        # Look up the current stock price
        quote = lookup(symbol)
        if not quote:
            return apology("Invalid symbol")

        # Calculate the total value of the sold shares
        total_value = quote["price"] * shares

        # Insert the sell transaction into the database
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, total, transaction_type) VALUES (?, ?, ?, ?, ?, ?)",
                   user_id, quote["symbol"], -shares, quote["price"], total_value, "sell")

        # Update user's cash
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?",
                   total_value, user_id)

        # Redirect to the home page
        return redirect("/")

    else:
        # If the request is a GET, render the sell form
        # Get the symbols of stocks the user owns
        user_id = session["user_id"]
        stocks_owned = db.execute(
            "SELECT DISTINCT symbol FROM transactions WHERE user_id = ? AND shares > 0", user_id)
        return render_template("sell.html", stocks_owned=stocks_owned)

# New route for the home page (portfolio)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Get user's id
    user_id = session["user_id"]

    # Query all user's transactions
    transactions = db.execute(
        "SELECT * FROM transactions WHERE user_id = ?", user_id)

    return render_template("history.html", transactions=transactions)


if __name__ == "__main__":
    app.run(debug=True)
