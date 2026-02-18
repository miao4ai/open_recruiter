"""CLI entry point — starts the Open Recruiter API server."""

import uvicorn


def main():
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
