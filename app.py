from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

import requests
import urllib
import xml.etree.ElementTree as ET


# Configure application
app = Flask(__name__)


# Configure session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///bgl.db")


def create_users():
    create_users = """CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    username TEXT NOT NULL,
                    hash TEXT NOT NULL
                    )"""
    db.execute(create_users)


def create_friends():
    create_friends = """CREATE TABLE IF NOT EXISTS friends (
                    user_id_1 INTEGER NOT NULL,
                    user_id_2 INTEGER NOT NULL,
                    status INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(user_id_1, user_id_2)
                    FOREIGN KEY(user_id_1) REFERENCES users(id),
                    FOREIGN KEY(user_id_2) REFERENCES users(id)
                    )"""
    # note status 0 means request pending, status 1 means accepted
    db.execute(create_friends)


def create_games():
    create_games = """CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY NOT NULL,
                    title TEXT NOT NULL
                    )"""
    db.execute(create_games)


def create_shelves():
    create_shelves = """CREATE TABLE IF NOT EXISTS shelves (
                    user_id INTEGER NOT NULL,
                    game_id INTEGER NOT NULL,
                    owned INTEGER NOT NULL DEFAULT 0,
                    rating INTEGER NOT NULL DEFAULT 0,
                    CHECK (rating >= 0 AND rating <= 10),
                    PRIMARY KEY(user_id, game_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(game_id) REFERENCES games(id)
                    )"""
    # note owned 0 means not owned, owned 1 means owned
    db.execute(create_shelves)


def create_temp_api_queries():
    create_temp_api_queries = """CREATE TABLE IF NOT EXISTS temp_api_queries (
                        temp_user_id INTEGER NOT NULL,
                        temp_game_id INTEGER NOT NULL,
                        temp_title TEXT NOT NULL,
                        PRIMARY KEY(temp_user_id, temp_game_id)
                        )"""
    db.execute(create_temp_api_queries)


create_users()
create_games()
create_shelves()
create_friends()
create_temp_api_queries()


# ensure responses aren't cached (taken from CS50 Finance)
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# error page shown when something goes wrong
def error(message):
    return render_template("error.html", message=message)


# Decorate routes to require login (based on similar from CS50 Finance assignment)
# https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
def requires_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


# LOG IN, LOG OUT, SIGN UP FUNCTIONS


# logs a user out when they click Log Out in the navbar
@app.route("/logout")
def logout():

    # clear the session
    session.clear()

    # redirect user to login page
    return redirect("/login")


# displays the login page when called
# also handles the procedure of logging in on the /login page
@app.route("/login", methods=["GET", "POST"])
def login():

    # clear the session
    session.clear()

    if request.method == "GET":
        return render_template("login.html")

    # else the method is POST

    # check for a submitted username
    if not request.form.get("username"):
        return error("username required")
    # check for a submitted password
    elif not request.form.get("password"):
        return error("password required")

    # query the db for the username
    rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

    # ensure username exists and pasword is correct
    if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
        return error("invalid username and/or password")

    # remember who is logged in
    session["user_id"] = rows[0]["id"]

    db.execute("DELETE FROM temp_api_queries WHERE temp_user_id = ?", session.get("user_id"))

    # redirect user to home page
    return redirect("/")


# displays the /signup page when called
# also handles the signup process on the /signup page
@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "GET":
        return render_template("signup.html")

    # else the method is POST

    username = request.form.get("username")
    password = request.form.get("password")
    confirmpassword = request.form.get("confirmpassword")

    if not username or len(username) > 20 or len(username) < 5 or " " in username:
        return error("username must be 5 to 20 characters long and contain no spaces")

    elif not password or len(password) > 20 or len(password) < 5:
        return error("password must be 5 to 20 characters long")

    elif confirmpassword != password:
        return error("passwords must match")

    # check if that username is already registered
    exists = db.execute("SELECT * FROM users WHERE username = ?", username)
    if len(exists) > 0:
        return error("username already exists")

    # create a hash of the password
    hash = generate_password_hash(password)

    # add user into users table
    # the value saved in key is the new user's primary key
    key = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)

    # remember which user is logged in
    session["user_id"] = key

    # redirect user to home page
    return redirect("/")


# HOMEPAGE

# shows homepage, including the number of games on your shelf, unique games in library, and friends
@app.route("/", methods=["GET"])
@requires_login
def index():

    username = db.execute("SELECT username FROM users WHERE id = ?", session.get("user_id"))[0]["username"]

    try:
        shelfgames = db.execute("SELECT COUNT(*) FROM shelves WHERE user_id = ? AND owned = 1", session.get("user_id"))
        # example: shelfgames = [{'COUNT(*)'}: 5]
        shelfgames = shelfgames[0]["COUNT(*)"]
        # example: shelfgames = 5
    except:
        shelfgames = 0

    try:
        friends = db.execute(
            "SELECT users.username, users.id FROM users JOIN friends ON friends.user_id_2 = users.id WHERE friends.user_id_1 = ? AND friends.status = 1 ORDER BY users.username", session.get("user_id"))
        numberfriends = len(friends)
    except:
        numberfriends = 0

    try:
        uniquegames = db.execute("SELECT DISTINCT shelves.game_id FROM shelves LEFT JOIN friends ON shelves.user_id = friends.user_id_2 WHERE (shelves.user_id = ? AND shelves.owned = 1) OR (shelves.owned = 1 AND shelves.user_id IN (SELECT user_id_2 FROM friends WHERE user_id_1 = ? AND status = 1))", session.get("user_id"), session.get("user_id"))
        librarygames = len(uniquegames)
    except:
        librarygames = 0

    return render_template("index.html", username=username, shelfgames=shelfgames, librarygames=librarygames, numberfriends=numberfriends)


# SHELF-RELATED FUNCTIONS


# displays your shelf page
# handles requests to sort your shelf by title or rating
@app.route("/your_shelf", methods=["GET", "POST"])
@requires_login
def your_shelf():

    try:
        numberofgames = db.execute("SELECT COUNT(*) FROM shelves WHERE user_id = ? AND owned = 1", session.get("user_id"))
        # example: numberofgames = [{'COUNT(*)'}: 5]
        numberofgames = numberofgames[0]["COUNT(*)"]
        # example: numberofgames = 5
    except:
        numberofgames = 0

    if request.method == "POST" and request.form.get("sortbyrating"):
        try:
            shelf = db.execute("SELECT games.title, shelves.game_id, shelves.rating FROM games JOIN shelves ON games.id = shelves.game_id WHERE shelves.user_id = ? AND shelves.owned = 1 ORDER BY shelves.rating DESC, games.title", session.get("user_id"))
            # example: shelf = [{'title': Codenames', 'game_id': 178900, 'rating': 10}, {'title': 'Azul', 'game_id': 230802, 'rating':0}]
        except:
            shelf = []

    else:
        try:
            shelf = db.execute("SELECT games.title, shelves.game_id, shelves.rating FROM games JOIN shelves ON games.id = shelves.game_id WHERE shelves.user_id = ? AND shelves.owned = 1 ORDER BY games.title, shelves.rating DESC", session.get("user_id"))
            # example: shelf = [{'title': 'Azul', 'game_id': 230802, 'rating':0}, {'title': Codenames', 'game_id': 178900, 'rating': 10}]
        except:
            shelf = []

    return render_template("your_shelf.html", shelf=shelf, numberofgames=numberofgames)


# handles deleting a game from your shelf while on your shelf page
@app.route("/deletegame", methods=["POST"])
@requires_login
def deletegame():

    game_id = request.form.get("delete_id")
    # set value of owned to 0, which keeps their rating available
    db.execute("UPDATE shelves SET owned = 0 WHERE user_id = ? AND game_id = ?", session.get("user_id"), game_id)

    return redirect("/your_shelf")


# handles rating a game
# can occur on your shelf page, on a friend's shelf page, and on your library page
@app.route("/rate", methods=["POST"])
@requires_login
def rate():

    jsonrating = request.get_json()

    try:
        db.execute("UPDATE shelves SET rating = ? WHERE user_id = ? AND game_id = ?",
                   jsonrating["rating"], session.get("user_id"), jsonrating["hiddenValue"])
    except:
        return error("invalid rating")

    return "rating updated"


# BGG API, SEARCH, AND ADD GAME FUNCTIONS


# displays the /add_games page
# also handles searching games while on the /add_games page
@app.route("/add_games", methods=["GET", "POST"])
@requires_login
def searchgames():
    if request.method == "GET":
        return render_template("add_games.html")

    # else it is POST
    if not request.form.get("searchname"):
        return error("must enter some text")
    results = lookup(request.form.get("searchname"))
    # results is XML data
    results_dict = {}
    # conver the XML data into a dictionary
    for child in results:
        id = child.get("id")
        name = child[0].get("value")
        results_dict[id] = name

    # clear any old entries in temp_api_queries to save space
    db.execute("DELETE FROM temp_api_queries WHERE temp_user_id = ?", session.get("user_id"))

    # add games to temp_api_queries
    for key, value in results_dict.items():
        db.execute("INSERT INTO temp_api_queries (temp_user_id, temp_game_id, temp_title) VALUES (?, ?, ?)",
                   session.get("user_id"), key, value)

    return render_template("add_games.html", results_dict=results_dict)


# handles running the actual API query that occurs on the /add_games page
# uses the Board Game Geek API to look up board game titles and their BGG ids
def lookup(game):
    # Board Game Geek API info at https://boardgamegeek.com/wiki/page/BGG_XML_API2

    # BGG API URL with + between words of lookup string
    url = (f"https://api.geekdo.com/xmlapi2/search?query={urllib.parse.quote_plus(game)}&type=boardgame")
    # example (you can type this in an address bar):
    # https://api.geekdo.com/xmlapi2/search?query=lords+of+waterdeep}&type=boardgame

    # Query API
    try:
        response = requests.get(url)
        root = ET.fromstring(response.text)
        # returns XML
        return root

    except (KeyError, IndexError, requests.RequestException, ValueError):
        return None


# handles selecting a game to add to a user's shelf from the search results on the /add_games page
@app.route("/search_results", methods=["POST"])
@requires_login
def search_results():

    if not request.form.get("results"):
        return error("must select a game to add")

    game_id = request.form.get("results")

    # make sure they haven't altered the game id
    exists_in_temp = db.execute(
        "SELECT temp_game_id, temp_title FROM temp_api_queries WHERE temp_game_id = ? AND temp_user_id = ?", game_id, session.get("user_id"))

    if len(exists_in_temp) == 0:
        return error("something went wrong with the game id")

    game_title = exists_in_temp[0]["temp_title"]

    # check if the game already exists in games
    exists = db.execute("SELECT id FROM games WHERE id = ?", game_id)
    # if not, add into table
    if len(exists) == 0:
        db.execute("INSERT INTO games (id, title) VALUES (?, ?)", game_id, game_title)

    # check if the user already has an entry for that game in shelves
    entry_in_shelf = db.execute(
        "SELECT user_id, game_id, owned FROM shelves WHERE user_id = ? AND game_id = ?", session.get("user_id"), game_id)

    # if no entries
    if len(entry_in_shelf) == 0:
        # add the game to their shelf as owned (default rating 0)
        db.execute("INSERT INTO shelves (user_id, game_id, owned) VALUES (?, ?, ?)", session.get("user_id"), game_id, 1)

    # if an entry but not owned (e.g., rated a friend's game previously)
    elif entry_in_shelf[0]["owned"] == 0:
        # update the entry so they now own it, keeping their existing rating
        db.execute("UPDATE shelves SET owned = 1 WHERE user_id = ? AND game_id = ?", session.get("user_id"), game_id)

    else:
        return error("you already own that game!")

    # clear their entries in temp_api_queries to save space
    db.execute("DELETE FROM temp_api_queries WHERE temp_user_id = ?", session.get("user_id"))

    return redirect("/add_games")


# FRIEND-RELATED FUNCTIONS


# displays the /friends page
@app.route("/friends", methods=["GET"])
@requires_login
def friends():

    friends = db.execute(
        "SELECT users.username, users.id FROM users JOIN friends ON friends.user_id_2 = users.id WHERE friends.user_id_1 = ? AND friends.status = 1 ORDER BY users.username", session.get("user_id"))

    incoming_requests = db.execute(
        "SELECT users.username, users.id FROM users JOIN friends ON users.id = friends.user_id_1 WHERE friends.user_id_2 = ? AND friends.status = ? ORDER BY users.username", session.get("user_id"), 0)

    outgoing_requests = db.execute(
        "SELECT users.username, users.id FROM users JOIN friends ON users.id = friends.user_id_2 WHERE friends.user_id_1 = ? AND friends.status = ? ORDER BY users.username", session.get("user_id"), 0)

    return render_template("friends.html", friends=friends, incoming_requests=incoming_requests, outgoing_requests=outgoing_requests)


# handles removing a friend while on the /friends page
@app.route("/removefriend", methods=["POST"])
@requires_login
def removefriend():

    db.execute("DELETE FROM friends WHERE user_id_1 = ? AND user_id_2 = ?", session.get("user_id"), request.form.get("delete_id"))

    db.execute("DELETE FROM friends WHERE user_id_1 = ? AND user_id_2 = ?", request.form.get("delete_id"), session.get("user_id"))

    return redirect("/friends")


# handles adding a friend while on the /friend_requests page
@app.route("/addfriend", methods=["POST"])
@requires_login
def addfriend():

    if not request.form.get("friendrequest"):
        return error("must enter a username")

    result = db.execute("SELECT id FROM users WHERE username = ?", request.form.get("friendrequest"))

    if not result:
        return error("username does not exist!")

    requested_user_id = result[0]["id"]

    if requested_user_id == session.get("user_id"):
        return error("that's your username!")

    try:
        db.execute("INSERT INTO friends (user_id_1, user_id_2, status) VALUES (?, ?, ?)",
                   session.get("user_id"), requested_user_id, 0)
    except ValueError as err:
        if err.args != ('UNIQUE constraint failed: friends.user_id_1, friends.user_id_2',):
            return error("already friends or pending")

    return redirect("/friends")


# handles rejecting, accepting, and cancelling requests on the /friend_requests page
@app.route("/manage_requests", methods=["POST"])
@requires_login
def manage_requests():

    if request.form.get("reject_request"):
        db.execute("DELETE FROM friends WHERE user_id_1 = ? AND user_id_2 = ?",
                   request.form.get("reject_request"), session.get("user_id"))

        # if user1 rejects a request from user2, check if they happen to have their own pending  outgoing request to user2 (though unlikely)
        reverse = db.execute("SELECT * FROM friends WHERE user_id_1 = ? AND user_id_2 = ?",
                             session.get("user_id"), request.form.get("reject_request"))

        # if so, get rid of that request
        if reverse:
            db.execute("DELETE FROM friends WHERE user_id_1 = ? AND user_id_2 = ?",
                       session.get("user_id"), request.form.get("reject_request"))

    elif request.form.get("accept_request"):
        db.execute("UPDATE friends SET status = ? WHERE user_id_1 = ? AND user_id_2 = ?",
                   1, request.form.get("accept_request"), session.get("user_id"))

        # if user1 accepts a request from user2, check if they also had a pending outgoing request to user2
        reverse = db.execute("SELECT * FROM friends WHERE user_id_1 = ? AND user_id_2 = ?",
                             session.get("user_id"), request.form.get("accept_request"))

        # if so, automatically accept that request (set status to 1)
        if reverse:
            db.execute("UPDATE friends SET status = ? WHERE user_id_1 = ? AND user_id_2 = ?",
                       1, session.get("user_id"), request.form.get("accept_request"))

        # otherwise, add an entry for the friendship in the other direction, so there is a separate entry for user1 being friends with user2, and vice versa.
        else:
            db.execute("INSERT INTO friends (user_id_1, user_id_2, status) VALUES (?, ?, ?)",
                       session.get("user_id"), request.form.get("accept_request"), 1)

    elif request.form.get("cancel_request"):
        db.execute("DELETE FROM friends WHERE user_id_1 = ? AND user_id_2 = ?",
                   session.get("user_id"), request.form.get("cancel_request"))

    return redirect("/friends")


# FRIEND SHELF FUNCTIONS


# displays the /friend_shelf page
# when a friend is selected, updates the /friend_shelf page to display that friend's shelf
@app.route("/friend_shelf", methods=["GET", "POST"])
@requires_login
def friend_shelf():

    friends = db.execute(
        "SELECT users.username, users.id FROM users JOIN friends ON friends.user_id_2 = users.id WHERE friends.user_id_1 = ? AND friends.status = 1 ORDER BY users.username", session.get("user_id"))

    if request.method == "GET":
        return render_template("friend_shelf.html", friends=friends, numberofgames=0, friendname="no_name")

    # else it is POST

    # get friend_id
    if request.form.get("sortbyfriendrating"):
        friend_id = request.form.get("sortbyfriendrating")
    elif request.form.get("sortbytitle"):
        friend_id = request.form.get("sortbytitle")
    elif request.form.get("sortbyyourrating"):
        friend_id = request.form.get("sortbyyourrating")
    else:
        friend_id = request.form.get("viewfriendshelf")

    if friend_id == None:
        return error("must select a username")

    # make sure they are friends before going any further
    check = db.execute("SELECT user_id_2 FROM friends WHERE user_id_1 = ? AND user_id_2 = ? AND friends.status = 1",
                       session.get("user_id"), friend_id)
    if not check:
        return error("must be friends to view their board game shelf")

    # find out which games owned by the friend do not already have entries by the current user
    game_entries = db.execute(
        "SELECT s1.game_id, s2.game_id as game_id2 FROM shelves s1 LEFT JOIN shelves s2 ON s1.game_id = s2.game_id AND s2.user_id = ? WHERE s1.user_id = ? AND s1.owned = 1", session.get("user_id"), friend_id)
    # example: game_entries = [{'game_id'}: 2453, 'game_id2': 2453'}, {'game_id': 217861, 'game_id2': None}]

    # add an entry into shelves (with default rating 0 and owned 0)
    # for the current user if there isn't already an entry
    for game in game_entries:
        if game["game_id2"] is None:
            db.execute("INSERT INTO shelves (user_id, game_id) VALUES (?, ?)", session.get("user_id"), game["game_id"])

    if request.form.get("sortbyfriendrating"):
        order1 = 's1.rating DESC'
        order2 = 's2.rating DESC'
        order3 = 'games.title'
    elif request.form.get("sortbyyourrating"):
        order1 = 's2.rating DESC'
        order2 = 's1.rating DESC'
        order3 = 'games.title'
    else:
        order1 = 'games.title'
        order2 = 's1.rating DESC'
        order3 = 's2.rating DESC'

    query = f"""SELECT games.title, s1.game_id, s1.rating as friendrating, s2.rating as yourrating FROM shelves s1 JOIN games ON s1.game_id = games.id LEFT JOIN shelves s2 ON s1.game_id = s2.game_id AND s2.user_id = ? WHERE s1.user_id = ? AND s1.owned = 1 ORDER BY {order1}, {order2}, {order3}"""
    friendshelf = db.execute(query, session.get("user_id"), friend_id)

    numberofgames = db.execute("SELECT COUNT(*) FROM shelves WHERE user_id = ? AND owned = 1", friend_id)
    # example: numberofgames = [{'COUNT(*)'}: 5]
    numberofgames = numberofgames[0]["COUNT(*)"]
    # example: numberofgames = 5

    friend_name = db.execute("SELECT username FROM users WHERE id = ?", friend_id)[0]["username"]

    return render_template("friend_shelf.html", friends=friends, numberofgames=numberofgames, friendshelf=friendshelf, friend_name=friend_name, friend_id=friend_id)


# LIBRARY FUNCTIONS


# displays the /library page
@app.route("/library", methods=["GET", "POST"])
@requires_login
def library():

    # find out which games owned by friends do not already have entries by the current user
    game_entries = db.execute("SELECT s1.game_id, s2.game_id as game_id2 FROM shelves s1 LEFT JOIN shelves s2 ON s1.game_id = s2.game_id AND s2.user_id = ? WHERE s1.user_id IN (SELECT friends.user_id_2 FROM friends WHERE friends.user_id_1 = ?) AND s1.owned = 1", session.get(
        "user_id"), session.get("user_id"))
    # example: game_entries = [{'game_id'}: 2453, 'game_id2': 2453'}, {'game_id': 217861, 'game_id2': None}]

    # add an entry into shelves (with default rating 0 and owned 0)
    # for the current user if there isn't already an entry
    for game in game_entries:
        if game["game_id2"] is None:
            try:
                db.execute("INSERT INTO shelves (user_id, game_id) VALUES (?, ?)", session.get("user_id"), game["game_id"])
            except ValueError:
                # already added in the value earlier in the loop
                pass

    # sorting options used in libraryquery1 below
    if request.form.get("sortbyyourrating"):
        order1 = 'shelves.rating DESC'
        order2 = 'games.title'
    else:
        order1 = 'games.title'
        order2 = 'shelves.rating DESC'

    # get all games (id, title) that you or your friends own, along with your rating and whether you own it
    libraryquery1 = f"""SELECT shelves.game_id, games.title, shelves.rating, CASE WHEN shelves.owned = 1 THEN 'Yes' ELSE 'No' END AS ownership FROM shelves JOIN games ON games.id = shelves.game_id WHERE shelves.user_id = ? AND shelves.game_id IN (SELECT DISTINCT shelves.game_id FROM shelves LEFT JOIN friends ON shelves.user_id = friends.user_id_2 WHERE (shelves.user_id = ? AND shelves.owned = 1) OR (shelves.owned = 1 AND shelves.user_id IN (SELECT user_id_2 FROM friends WHERE user_id_1 = ? AND status = 1))) ORDER BY {order1}, {order2}"""

    library = db.execute(libraryquery1, session.get("user_id"), session.get("user_id"), session.get("user_id"))
    # example library = [{'game_id': 2453, 'title': 'Blokus', 'rating': 7, 'ownership': 'Yes'}, {'game_id: ...}]

    # this is the number of unique games
    numberofgames = len(library)

    # find ids of the games that your friends own, along with friend ids and usernames
    libraryquery2 = db.execute("SELECT shelves.game_id, shelves.user_id, users.username FROM shelves JOIN users ON shelves.user_id = users.id WHERE shelves.owned = 1 AND shelves.user_id IN (SELECT shelves.user_id FROM shelves JOIN friends ON shelves.user_id = friends.user_id_2 WHERE friends.user_id_1 = ? AND friends.status = 1) ORDER BY users.username", session.get("user_id"))
    # example libraryquery2 = [{'game_id': 2453, 'user_id': 2, 'username': 'user2'}, {'game_id': 2453, 'user_id': 3, 'username': 'user3'}, ...]

    groupedbygame_lq2 = {}
    for entry in libraryquery2:
        if entry['game_id'] not in groupedbygame_lq2.keys():
            groupedbygame_lq2[entry['game_id']] = []
        groupedbygame_lq2[entry['game_id']].append(entry['username'])
    # example groupedbygame_lq2 = {2453: ['user2', 'user3'], 11971: ['user3'], ...}

    for entry in library:
        if entry['ownership'] == 'Yes':
            entry['ownedby'] = ['You']
        else:
            entry['ownedby'] = []

        if entry['game_id'] in groupedbygame_lq2.keys():
            entry['ownedby'] = groupedbygame_lq2[entry['game_id']]
        # else case not expected
        else:
            entry['ownedby'] = []
        if entry['ownership'] == 'Yes':
            entry['ownedby'].insert(0, 'You')
    # example library = [{'game_id': 2453, 'title': 'Blokus', 'rating': 7, 'ownership': Yes', ownedby: ['You', 'user2', 'user3']}, {'game_id: ...}]

    return render_template("library.html", library=library, numberofgames=numberofgames)
