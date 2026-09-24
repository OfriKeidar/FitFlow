from dotenv import load_dotenv

# Read secrets (ANTHROPIC_API_KEY, JWT_SECRET...) from a local .env file into the environment.
# The .env file is in .gitignore, so secrets never reach git. Variables that are already set win.
load_dotenv()
