from sqlalchemy import text

from app.core.database import engine


print("Starting database connection test...")

try:
    with engine.connect() as connection:
        print("Connection established.")

        result = connection.execute(text("SELECT version()"))
        version = result.scalar()

        print("PostgreSQL version:")
        print(version)

except Exception as error:
    print("DATABASE CONNECTION FAILED")
    print(type(error).__name__)
    print(error)