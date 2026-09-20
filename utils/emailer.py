import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging
from dotenv import load_dotenv

# Configure logging     
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def send_email(content: str, receiver_email: str) -> bool:
    """
    Sends the generated news summary via email using smtplib.
    
    Args:
        content (str): The body text (the summarized news) to be emailed.
        receiver_email (str): The address to send the email to.
        
    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    if not content:
        logger.warning("No summary text provided to send.")
        return False
        
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    if not sender_email or not sender_password:
        logger.error("Email credentials missing. Please define `SENDER_EMAIL` and `SENDER_PASSWORD` in your .env file.")
        return False
        
    if not receiver_email:
        logger.error("No receiver email provided.")
        return False

    # Prepare the email headers and body
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "Daily News Summary"
    
    # We're sending plain text since markdown often requires complex HTML conversions for email clients
    msg.attach(MIMEText(content, 'plain'))
    
    try:
        logger.info(f"Connecting to SMTP server to email {receiver_email}...")
        
        # Allowing server/port defaults for standard Gmail implementation
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls() # Secure the connection
            server.login(sender_email, sender_password)
            server.send_message(msg)
            
        logger.info("News summary email successfully sent!")
        return True
        
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP Authentication Failed. Please check your credentials. If using Gmail, you may need to generate an 'App Password'.")
        return False
    except Exception as e:
        logger.error(f"Failed to send email due to an unexpected error: {e}")
        return False

# Example usage
if __name__ == "__main__":
    test_summary = "This is an autonomous test email from the Antigravity News System!\n\nTrending: Space, AI, Economics."
    send_email(test_summary, "test@example.com")
