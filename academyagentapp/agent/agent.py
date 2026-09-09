# imports
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Annotated, Sequence, TypedDict, Literal
from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel, Field
import os, requests, functools, csv
from academyagentapp.category_enum import CanonCategoryEnum
import json
from academyagentapp import app

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")
dataset_path = os.path.join(app.root_path, "agent", "oscars.csv")


# add the state
class State(TypedDict):
    """The state of the agent"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: Literal["end", "tool"] | None


# This caches the oscar data, cause the oscar data is static (static until the oscars are hosted again, this happens annually)
@functools.cache
def _load_oscars() -> list[dict]:
    with open(dataset_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


################################
# FUNCTION (TOOL) DECLARATIONS #
################################

class OscarWinnerInput(BaseModel):
    start_year: int = Field(
        description="The lower bound year of oscar winners (inclusive)"
    )
    end_year: int = Field(
        description="The upper bound year of oscar winners (inclusive)"
    )
    category: CanonCategoryEnum | None = Field(
        description="The category to filter by"
    )


@tool(args_schema=OscarWinnerInput)
def get_oscar_winners(start_year: int, end_year: int, category: str = None) -> list[dict]:
    """
        Returns a list of films that have won an oscar and that we're released between two years (inclusive). If a category is provided, it will only return films that have won in that category.

        Returns:
        - list of dicts, each dict contains the following keys:
            - film: str, the name of the film
            - film_id: str, the IMDB id of the film
            - category: str, the category of the award
            - year: int, the year of the award
            - winner_names: str, name(s) of the nominee(s) who won the award, contributed to the award or were associated with the award. If there are multiple names, they will be separated by a comma
            - winner: str, "True" if the film won, "False" otherwise

        Notes:
        - This function will consider films that were released in the year provided, not the year the award was given. For example: 2022 means films released in 2022 NOT award given in 2022
    """

    start_year, end_year = sorted((start_year, end_year))  # sort the years so that start_year <= end_year
    rows = _load_oscars()  # only reads disk on the very first call
    results = []
    for row in rows:
        if row["Winner"] != "True":  # check if the row is a winner
            continue
        try:
            year = int(row["Year"][:4])
        except ValueError:
            continue
        if not (start_year <= year <= end_year):  # check if the year is in the range
            continue
        if category and row["CanonicalCategory"] != category.upper():  # check if the category matches
            continue
        film_ids = row["FilmId"].split("|") if row["FilmId"] and row["FilmId"] != "?" else []
        films = row["Film"].split("|") if row["Film"] else []
        for film, film_id in zip(films, film_ids):
            results.append({"film": film, "film_id": film_id, "category": row["CanonicalCategory"], "year": year,
                            "winner_names": row["Name"], "winner": "True"})
    return results


# TRY TO MAKE THIS TOOL MORE RELIABLE. GIVING ERRORS. SOMETHING TO DO WITH QUERIES THAT DONT MATCH EXACT TITLE
class WikiMediaInput(BaseModel):
    query: str = Field(
        description="The search query. DO NOT USE IT LIKE A CUSTOM GOOGLE SEARCH. DO NOT BE OVERLY SPECIFIC AS IT MAY NOT MATCH A WIKIPEDIA PAGE TITLE."
    )


@tool(args_schema=WikiMediaInput)
def general_search_wikipedia(query: str) -> str:
    """
        Calls WikiMedia API with the query string. Returns the first page of wikipedia (in WikiText format) on the topic provided in the query string

        Returns:
        - str, the first page of wikipedia

        Notes:
        - An ambiguous or non-matching search query can prompt a #REDIRECT in the returned content. Recall this tool with the content inside the double square brackets as the new query string
    """

    url = "https://en.wikipedia.org/w/api.php"
    headers = {"User-Agent": "TryingThisAPIOut/1.0 (mptaylor2@sheffield.ac.uk)"}
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvsection": 0,
        "titles": query,
        "format": "json"
    }
    response = requests.get(url, headers=headers, params=params)
    res = response.json()
    try:
        pages = res["query"]["pages"]
        revision = pages[next(iter(pages))]["revisions"][0]["*"]
    except Exception as e:
        print("BRO FRICKING WIKI")
        revision = json.dumps(res)

        # print(str(e.with_traceback()))
        print(revision)
    return revision


@tool
def birth_death_dates_wikipedia(person: str) -> dict:
    """
        Returns the birth and death dates of a person, given they have a wikipedia page. The information will be fetched from WikiMedia API

        Inputs:
        - person: str, the name of the person

        Outputs:
        - dict, containing the following keys:
            - 'name' : str, the name of the person
            - 'birth_date' : str, the birth date of the person in YYYY/MM/DD format
            - 'death_date' : str, the death date of the person in YYYY/MM/DD format.

        Notes:
        - If the wikipedia page is not found, an error message will be returned
    """

    wiki_revision = general_search_wikipedia.invoke(person).replace(" ", "")
    birth_date = get_birth_date(wiki_revision).get("birth_date")
    death_date = get_death_date(wiki_revision).get("death_date")

    return_obj = {
        "name": person,
        "birth_date": birth_date,
        "death_date": death_date
    }

    return return_obj


# HELPER FUNCTIONS FOR BIRTH AND DEATH DATE
def get_birth_date(content: str) -> dict:  # n = 10
    birth_date_start = content.find(
        "birth_date")  # bds is the start of the 'birth_date' keyword in the infobox section of the wiki page
    if birth_date_start > -1:
        try:
            values = content[birth_date_start + 11: content.find("\n", birth_date_start)].replace("}", "").split("|")[
                -3:]  # this extracts the birth date from pipe seperated values
            if not values:
                raise Exception("Unsual Format")
            values_2digit = map(lambda x: f"{int(x):02d}", values)
            birth_date = "/".join(values_2digit)
            return {"birth_date": birth_date}
        except Exception as e:
            return {"birth_date": content[birth_date_start + 11: content.find("\n", birth_date_start)]}
    else:
        return {"error": "birth date not found."}


def get_death_date(content: str) -> dict:  # n = 10
    death_date_start = content.find(
        "death_date")  # dds is the start of the 'death_date' keyword in the infobox section of the wiki page
    if death_date_start > -1:
        try:
            values = content[death_date_start + 11: content.find("\n", death_date_start)].replace("}", "").split("|")[
                -6:-3]  # this extracts the death date from pipe seperated values
            if not values:
                raise Exception("Unusual format")
            values_2digit = map(lambda x: f"{int(x):02d}", values)
            death_date = "/".join(values_2digit)
            return {"death_date": death_date}
        except Exception as e:
            return {"death_date": content[death_date_start + 11: content.find("\n", death_date_start)]}
    else:
        return {"error": "death date not found. Probably still alive"}


# toolkit
toolkit = [get_oscar_winners, general_search_wikipedia, birth_death_dates_wikipedia]
tool_map = {
    "get_oscar_winners": get_oscar_winners,
    "general_search_wikipedia": general_search_wikipedia,
    "birth_death_dates_wikipedia": birth_death_dates_wikipedia
}

# instantiate the LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    google_api_key=api_key
)

model = llm.bind_tools(toolkit)


# construct the nodes/functions
def call_tools(state: State):
    # get the tool call
    # print("Called tool")
    # print(state)
    last_message = state["messages"][-1]
    outputs = []
    # loop through the tool calls
    for tool_call in last_message.tool_calls:
        # execute the tool
        # ADD TOOL ERROR HANDLING HERE
        try:
            tool_result = tool_map[tool_call["name"]].invoke(tool_call["args"])
        except Exception as e:
            print("WTF ERROR BRO HONESTLY SO CONFUSED RN", str(e))
            tool_result = {"error": str(e)}
        # append result to messages
        outputs.append(
            ToolMessage(
                content=tool_result,
                name=tool_call["name"],
                tool_call_id=tool_call["id"]
            )
        )
        print(f"TOOL CALLED! (Possible errors):\n{outputs[-1]}")

    return {"messages": outputs}


def call_llm(state: State):
    # call the model with the current message history
    response = model.invoke(state["messages"])
    print(f"LLM:\n{response}")
    # return the response
    return {"messages": [response]}


def router(state: State):
    last_message = state["messages"][-1]
    # If the last message is not a tool call, then finish
    print("ROUTER DETERMINING...")
    if not last_message.tool_calls:  # or last_message.tool_calls[0].content.get("error") is not None:
        return {"next": "end"}
    # default to continue
    return {"next": "tool"}


# construct the graph
graph_builder = StateGraph(State)

# add nodes to the graph
graph_builder.add_node("llm", call_llm)
graph_builder.add_node("tool_call", call_tools)
graph_builder.add_node("router", router)

# add edges to the graph
graph_builder.add_edge(START, "llm")
graph_builder.add_edge("llm", "router")
graph_builder.add_conditional_edges(
    "router",
    lambda state: state.get("next"),
    path_map={"end": END, "tool": "tool_call"}
)
graph_builder.add_edge("tool_call", "llm")

graph = graph_builder.compile()

state = {"messages": [], "next": None}


class AcademyAgent:
    compiled_graph = graph
    default_state = {"messages": [], "next": None}

    def __init__(self, _state=None):
        self.state = _state if _state else self.default_state

    @classmethod
    def zero_shot_query(cls, query: str) -> str:
        state = cls.default_state.copy()
        state["messages"] = [("user", query + ". DO NOT USE ANY TOOLS.")]

        state = cls.compiled_graph.invoke(state)

        message = state["messages"][-1].content[0]["text"]

        return message
