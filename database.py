import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "mysql+pymysql://root:Hardik%402827@localhost:3306/fintech_credit_simulator"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Dependency to get database session
def get_db():
    """Database session dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Fixed test database connection function
def test_database_connection():
    """Test database connectivity"""
    try:
        with engine.connect() as connection:
            # Test basic connectivity - FIXED: wrap SQL in text()
            result = connection.execute(text("SELECT 1 as test"))
            print("✅ MySQL connection successful!")
            
            # Try to use the database
            try:
                connection.execute(text("USE fintech_credit_simulator"))
                print("✅ Database 'fintech_credit_simulator' accessible!")
            except Exception as db_error:
                print(f"⚠️  Database 'fintech_credit_simulator' not found: {db_error}")
                print("💡 Creating database...")
                # Try to create the database
                try:
                    connection.execute(text("CREATE DATABASE fintech_credit_simulator"))
                    print("✅ Database 'fintech_credit_simulator' created!")
                except Exception as create_error:
                    print(f"❌ Could not create database: {create_error}")
                    return False
            
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

