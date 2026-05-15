"""Password hashing and verification utilities using bcrypt."""

from passlib.context import CryptContext

# Configure bcrypt as the password hashing algorithm (industry standard for security)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash(password: str):
    """Hash a plaintext password using bcrypt.
    
    Args:
        password: Plain text password string
        
    Returns:
        Hashed password string (safe to store in database)
    """
    return pwd_context.hash(password)


def verify(plain_password, hashed_password):
    """Verify a plaintext password against its bcrypt hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Previously hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)
