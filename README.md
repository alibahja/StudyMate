# StudyMate

StudyMate turns a lecture document into a full set of study materials. Upload a PDF or Word file, and a pipeline of coordinated AI agents generates an explanation, a summary, multiple-choice questions, subjective questions, and a solution key for it.

It's built on LangGraph for the agent pipeline, FastAPI for the backend, and MCP for tool integration — with Groq handling inference and a Postgres database keeping track of users and past sessions.

**Live demo:** [studymate-qnj7.onrender.com](https://studymate-qnj7.onrender.com)

---

## What it does

Each upload runs through five specialized agents:

- **Explanation agent** — breaks the material down into plain-language explanations
- **Summary agent** — condenses it into the key points
- **MCQ agent** — writes multiple-choice questions to test recall
- **Subjective agent** — writes open-ended questions that require actual reasoning
- **Solutions agent** — produces worked answers for everything generated above

A few things around that core pipeline:

- Model routing picks the best available Groq model for each task based on complexity and current quota, so a rate limit on one model doesn't take the whole pipeline down
- Accounts are required, so your study history stays yours
- Past sessions are saved and browsable from a history page, with each one re-downloadable
- Everything generated gets bundled into a formatted PDF you can export

## Stack

| Layer | Tool |
|---|---|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) |
| Agent orchestration | [LangGraph](https://www.langchain.com/langgraph) |
| Tool integration | [MCP](https://modelcontextprotocol.io/) |
| Inference | [Groq](https://groq.com/) |
| Database | [PostgreSQL](https://www.postgresql.org/) |
| Deployment | Docker on [Render](https://render.com/) |

## Running it locally

**Prerequisites:** Python 3.11+, a PostgreSQL instance, and a Groq API key.

```bash
git clone https://github.com/alibahja/StudyMate.git
cd StudyMate

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://user:password@host:port/database
GROQ_API_KEY=your_groq_api_key
```

Set up the database by running the SQL in the project docs to create the `users`, `sessions`, and `study_sessions` tables, then start the app:

```bash
python app.py
```

It'll be running at `http://localhost:8000`.

## Roadmap

- Support for additional LLM providers (Gemini, OpenAI) alongside Groq
- OCR support, so scanned or image-based PDFs work too
- Password reset and stronger auth flows
- Response caching to cut down on redundant API calls

## License

MIT — see [LICENSE](LICENSE) for details.

## Author

**Ali Bahja**
GitHub: [@alibahja](https://github.com/alibahja)

## Acknowledgements

Built with [LangChain](https://www.langchain.com/) and [Groq](https://groq.com/), and the broader open-source ecosystem that makes projects like this possible to build solo.
