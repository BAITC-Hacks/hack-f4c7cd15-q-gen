"""Server launcher for MoneyGraph AML Intelligence API."""
import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run MoneyGraph AML FastAPI Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable hot reloading for development")
    args = parser.parse_args()

    print(f"MoneyGraph AML API starting on http://{args.host}:{args.port}")
    print(f"Interactive Swagger Documentation: http://127.0.0.1:{args.port}/docs")
    print(f"ReDoc Documentation: http://127.0.0.1:{args.port}/redoc")
    print(f"Interactive Web Dashboard: http://127.0.0.1:{args.port}/analytics")

    uvicorn.run("api.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
