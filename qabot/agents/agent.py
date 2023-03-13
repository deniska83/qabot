import textwrap

from langchain import LLMMathChain
from langchain.agents import Tool, initialize_agent
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAIChat
from langchain.memory import ConversationBufferMemory

from qabot.agents.data_query_chain import get_duckdb_data_query_chain
from qabot.duckdb_query import run_sql_catch_error
from qabot.tools.describe_duckdb_table import describe_table_or_view


def create_agent_executor(
        database_engine=None,
        tables=None,
        return_intermediate_steps=False,
        callback_manager=None,
        verbose=False,
):

    llm = OpenAIChat(
        model_name="gpt-3.5-turbo",
        temperature=0.0
    )

    # llm = ChatOpenAI(
    #     model_name="gpt-3.5-turbo",
    #     temperature=0.0
    # )

    python_chain = LLMMathChain(llm=llm, verbose=False)

    db_chain = get_duckdb_data_query_chain(
        llm=llm,
        database=database_engine,
        callback_manager=callback_manager,
        verbose=verbose
    )

    tools = [
        Tool(
            name="Python",
            func=python_chain.run,
            description="Useful for when you need to run a quick simulation, or answer questions about math"
        ),
        # Tool(
        #     name="DuckDB QA System",
        #     func=duckdb_docs_qa_chain.run,
        #     description="useful for when you need to answer questions about duckdb. Input should be a fully formed question."
        # ),
        Tool(
            name="Show Tables",
            func=lambda _: run_sql_catch_error(database_engine, "show tables"),
            description="Useful to show the available tables and views. Empty input required."
        ),
        Tool(
            name="Describe Table",
            func=lambda table: describe_table_or_view(database_engine, table),
            description="Useful to show the column names and types of a table or view. Use the table name as the input."
        ),
        Tool(
            name="Data Op",
            func=lambda input: db_chain({
                'table_names': lambda _: run_sql_catch_error(database_engine, "show tables;"),
                'input': input}),
            description=textwrap.dedent("""Useful for when you need to operate on data and answer individual questions
            requiring data. Input should be in the form of a natural language question containing full context
            including what tables and columns are relevant to the question. Use only after data is present and loaded.
            Prefer to take small independent steps with this tool.
            """,)
        )
    ]

    memory = ConversationBufferMemory(memory_key="chat_history", output_key="output")

    agent = initialize_agent(
        tools,
        llm,
        agent="conversational-react-description",
        callback_manager=callback_manager,
        return_intermediate_steps=return_intermediate_steps,
        verbose=verbose,
        agent_kwargs={
            #"input_variables": ["input", 'agent_scratchpad', 'chat_history'],
            "prefix": prompt_prefix_template
        },
        memory=memory
    )
    return agent


prompt_prefix_template = """Qabot is a large language model trained to interact with DuckDB.

Qabot is designed to be able to assist with a wide range of tasks, from answering simple questions to providing in-depth explorations on a wide range of topics relating to data.

Qabot answers questions by first querying for data to guide its answer. Qabot asks any clarifying questions it needs to.

Qabot refuses to delete any data, or drop tables. 

Qabot prefers to split questions into small discrete steps, for example creating views of data as one action, then selecting data from the created view to get to the final answer.

Qabot includes a list of all important SQL queries returned by Data Op in its final answers.

Qabot does NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.

If the question does not seem related to the database, Qabot returns "I don't know" as the answer.
TOOLS:
------

Qabot has access to the following tools:
"""
