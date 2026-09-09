from flask import render_template, request, make_response, session, redirect
from academyagentapp.agent.agent import graph_builder
from academyagentapp import app, db
from academyagentapp.model import Users
from langgraph.checkpoint.sqlite import SqliteSaver
import markdown, hashlib, sqlite3, os
from random import random

# connecting to db
db_path = "..\\AcademyAwardsAgent\\instance\\site.db"
print("DB PATH:", db_path)
conn = sqlite3.connect(db_path, check_same_thread=False)
memory = SqliteSaver(conn)

checkpointed_graph = graph_builder.compile(checkpointer=memory)

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect("/login")

    print(session)
    response = make_response(render_template("index.html", username=Users.get_username(session.get("user_id"))))

    session_cookie = request.cookies.get("session_id")

    if not session_cookie:
        response.set_cookie("session_id", generate_session_hash(), max_age=60 * 60)  # this is in seconds
        db.session.commit()

    return response


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect("/")

    # get username, password and login type
    error_dict = {}
    if request.method == "POST":
        form_data = request.form
        print("FORM DATA:", form_data)

        username = form_data.get("username", None)
        password = form_data.get("password", None)
        password_confirm = form_data.get("password_confirm", None)
        mode = form_data.get("login_mode", None)

        if mode == "login":
            # check if username is in db, if it is check if the password is the same, if same login the user
            query = db.select(Users).where(Users.username == username).where(Users.password == password)
            user = db.session.scalars(query).first()
            # checking for errors in the form data
            if not user:
                error_dict["username"] = "Username or password is incorrect"
                error_dict["password"] = "Username or password is incorrect"

            if not error_dict:
                session["user_id"] = user.id
                return redirect("/")

        elif mode == "signup":
            query = db.select(Users).where(Users.username == username)
            user = db.session.scalars(query).first()

            # checking for errors in the form data
            if user is not None:
                error_dict["username"] = "Username is taken"
            if password != password_confirm:
                error_dict["password"] = "Passwords do not match"
                error_dict["password_confirm"] = "Passwords do not match"

            # if username is not in the db, make a new user obj and insert into db
            if not error_dict:
                new_user = Users(username=username, password=password)
                db.session.add(new_user)
                db.session.commit()
                session["user_id"] = new_user.id
                return redirect("/")

    print("ERROR DICT:", error_dict)
    response = make_response(
        render_template("login.html", error_dict=error_dict, mode=mode if request.method == "POST" else "login"))
    return response


@app.route("/agent", methods=["POST"])
def agent_response():
    # get frontend data
    res = request.get_json()
    # extract user query and session_id
    query: str = res.get("query", "")
    session_id: str = res.get("session_id", "")
    # invoke agent if query not empty
    if query.strip() == "":
        return {"response": "Please enter a valid query."}

    # define state and config
    state = {"messages": [("user", query)], "next": None}
    config = {"configurable": {"thread_id": session_id}}
    response = checkpointed_graph.invoke(state, config=config)
    ai_response = response["messages"][-1].content[0]["text"]

    print("RJESPONSE:", ai_response)
    # convert response into html markdown
    html_response = add_header_sizing(markdown.markdown(ai_response, output_format="html", extensions=['fenced_code']))
    print("HTML RESP:", html_response)
    return {"response": html_response}


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


def generate_session_hash(data=None):
    if data is None:
        data = str(random())
        print(data)
    sha1_hasher = hashlib.sha1()
    sha1_hasher.update(data.encode("utf-8"))
    digest = sha1_hasher.hexdigest()

    return digest


def add_header_sizing(html: str):
    # h1 tags
    html = html.replace("<h1>", "<h1 class='text-4xl font-bold'>")
    # h2 tags
    html = html.replace("<h2>", "<h2 class='text-3xl font-bold'>")
    # h3 tags
    html = html.replace("<h3>", "<h3 class='text-2xl font-bold'>")
    # h4 tags
    html = html.replace("<h4>", "<h4 class='text-xl font-semibold'>")

    return html

