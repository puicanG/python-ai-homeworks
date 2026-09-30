import os
import json
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# lista de tools pe care le primeste LLM-ul.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Lists all files in the project. Call this tool FIRST, before searching.",
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_keyword",
            "description": "Searches a keyword inside the content of the project files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "The keyword searched in the project files.",
                    }
                },
                "required": ["keyword"],
            },
        },
    },
]


# def tool no 1: listeaza toate fisierele din proiect, cu "dir /s".
def list_files() -> str:
    result = subprocess.run(
        "dir /s /b /a-d",
        shell=True,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # scoatem fisierele din .venv si din cache, ca sa nu fie lista prea lunga.
    files = [line for line in result.stdout.splitlines() if line.strip()]
    files = [f for f in files if ".venv" not in f and "__pycache__" not in f]

    if not files:
        return "No files found in the project."

    return f"Found {len(files)} files in the project:\n" + "\n".join(files)


# def tool no 2: cauta un cuvant cheie in continutul fisierelor, cu "findstr".
def search_keyword(keyword: str) -> str:
    result = subprocess.run(
        # cautam doar in fisierele de text, ca sa nu intram in celelalte fisierele (.pyc).
        f'findstr /s /i "{keyword}" *.py *.toml *.txt *.json *.md *.lock *.cfg *.ini',
        shell=True,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        errors="ignore",
        timeout=120,
    )

    # findstr afiseaza linii de forma "nume_fisier".
    lines = [line for line in result.stdout.splitlines() if line.strip()]

    if not lines:
        return f"The keyword '{keyword}' was not found in the project."

    # se pastreaza doar numele fisierelor in care a fost gasit cuvantul cheie.
    file_names = []
    for line in lines:
        name = line.split(":")[0]
        if name not in file_names:
            file_names.append(name)

    # se ignora .venv si cache-urile
    file_names = [f for f in file_names if ".venv" not in f and "__pycache__" not in f and ".pytest_cache" not in f]

    return f"The keyword '{keyword}' was found in {len(file_names)} files:\n" + "\n".join(file_names)


# trimitem mesajele la LLM si primim raspunsul.
def complete(client: OpenAI, messages: list[dict]):
    return client.chat.completions.create(
        messages=messages,
        model=os.getenv("OPEN_ROUTER_MODEL_NAME"),
        tools=TOOLS,
        tool_choice="auto",
    ).choices[0].message


def main():
    # incarcam cheia API din fisierul .env
    load_dotenv()

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPEN_ROUTER_API_KEY"),
    )

    messages = [
        {
            "role": "system",
            "content": "You are a coding agent. For every search follow these steps in this order: "
            "1) first you call the list_files tool; 2) after that you call the search_keyword tool. "
            "Do not search before listing the files. At the end tell the user in which files you found the keyword.",
        }
    ]

    # bucla de mesaje merge pana cand utilizatorul scrie "quit".
    while True:
        question = input("you> ")

        if question == "quit":
            break

        messages.append({"role": "user", "content": question})

        # boolean care ne va spune daca unealta list_files a fost deja apelata.
        has_listed = False

        # se intreaba modelul si se executa tools pana cand ne da un text normal.
        while True:
            response = complete(client, messages)

            message = {"role": "assistant", "content": response.content or ""}

            # tool_calls este o lista. Daca nu este goala, inseamna ca LLM-ul cere sa
            # se ruleze unul sau mai multe tools, iar noi trebuie sa-i raspundem cu rezultatele.
            if response.tool_calls:
                message["tool_calls"] = []

                # transformam fiecare apel de tools in formatul dict cerut de API.
                for call in response.tool_calls:
                    message["tool_calls"].append({
                        "id": call.id,                              # id-ul apelului, trebuie raspuns cu el.
                        "type": "function",
                        "function": {
                            "name": call.function.name,             # numele tool-ului, ex: "list_files".
                            "arguments": call.function.arguments,   # argumentele, ca text JSON.
                        },
                    })

            messages.append(message)

            # daca LLM-ul nu mai cere nici un tool, atunci asta e raspunsul final.
            if not response.tool_calls:
                break

            for call in response.tool_calls:
                tool_name = call.function.name
                arguments = json.loads(call.function.arguments or "{}")

                if tool_name == "list_files":
                    tool_result = list_files()
                    has_listed = True
                elif tool_name == "search_keyword":
                    # daca nu s-au listat inca fisierele, il oprim si ii zicem sa o faca
                    if has_listed:
                        tool_result = search_keyword(arguments.get("keyword", ""))
                    else:
                        tool_result = "Call the list_files tool first, then search again."
                else:
                    tool_result = f"error: unknown tool {tool_name}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": tool_result,
                })

        print("agent> ", response.content)


if __name__ == "__main__":
    main()
