"""
resume_parser.py

This module is responsible for parsing resume files (DOCX and PDF) to extract raw text
and then attempting to identify and extract common pieces of information such as
name, email, phone number, LinkedIn profile, and GitHub profile using regex patterns.

For more advanced and accurate parsing (e.g., identifying sections like experience,
education, skills, or handling complex layouts), integration with a dedicated
NLP library (like spaCy) or an AI-powered resume parsing service would be necessary.
The current implementation provides a basic level of information extraction.
"""
import io
import re
import os # Added for testing block
from docx import Document
from pdfminer.high_level import extract_text as extract_pdf_text
from pdfminer.layout import LAParams

def _parse_docx(file_stream):
    """
    Extracts all text content from a DOCX file stream.

    Args:
        file_stream (io.BytesIO): A byte stream of the DOCX file content.

    Returns:
        tuple: (text, error_message)
               - text (str): The extracted text from the document, with paragraphs joined by newlines.
               - error_message (str or None): An error message if parsing fails, otherwise None.
    """
    try:
        document = Document(file_stream)
        text = "\n".join([para.text for para in document.paragraphs if para.text]) # Ensure para.text is not None
        return text, None
    except Exception as e:
        return None, f"Error parsing DOCX: {e}"

def _parse_pdf(file_stream):
    """
    Extracts all text content from a PDF file stream using pdfminer.six.

    Args:
        file_stream (io.BytesIO): A byte stream of the PDF file content.

    Returns:
        tuple: (text, error_message)
               - text (str): The extracted text from the PDF.
               - error_message (str or None): An error message if parsing fails, otherwise None.
    """
    try:
        # LAParams can be adjusted for more precise layout analysis if default extraction is poor.
        text = extract_pdf_text(file_stream, laparams=LAParams())
        return text, None
    except Exception as e:
        return None, f"Error parsing PDF: {e}"

def _extract_name(text):
    """
    Attempts to extract a person's name from the resume text.

    This is a very naive heuristic approach and has significant limitations:
    - Looks for 2-3 capitalized words (e.g., "John Doe", "Jane A. Doe") at the beginning
      of the first few lines of the text.
    - Has a fallback to search for a line starting with "Name:".
    - Highly dependent on resume formatting and common English name structures.
    - Will not perform well with non-standard names, formats, or languages.

    Args:
        text (str): The full text of the resume.

    Returns:
        str or None: The extracted name string if found, otherwise None.
    """
    # Try to find lines with 2-3 capitalized words, often at the start of the resume
    for line in text.split('\n')[:10]: # Check the first 10 lines
        line = line.strip()
        if not line: # Skip empty lines
            continue

        # Regex for two or three capitalized words, optionally with a middle initial.
        # Example: "John Doe", "Jane A. Doe", "Mary-Anne Smith" (hyphenated names are tricky here)
        # This regex is basic and might need refinement for more complex name structures.
        match = re.match(r'^([A-Z][a-z]+(?: [A-Z]\.)? [A-Z][a-z]+(?:-[A-Z][a-z]+)?)$', line)
        if match:
            return match.group(1)

        # Simpler regex for exactly two capitalized words.
        match_simple = re.match(r'^([A-Z][a-z]+ [A-Z][a-z]+)$', line)
        if match_simple:
            return match_simple.group(1)

    # Fallback: Look for "Name:" pattern (less common in modern resumes, but a possible fallback)
    # This is broad and might pick up other "Name:" fields if they exist.
    name_pattern = re.compile(r"^(?:name|full\s*name)\s*[:\-]\s*([A-Za-z\s.'-]+)", re.IGNORECASE | re.MULTILINE)
    name_search = name_pattern.search(text)
    if name_search:
        # Further clean up common leading/trailing issues if any.
        extracted_name = name_search.group(1).strip()
        # Avoid excessively long strings that are unlikely to be names
        if len(extracted_name.split()) <= 4 and len(extracted_name) < 50:
             return extracted_name

    return None


def _extract_email(text):
    """
    Extracts the first valid email address found in the text using a regex pattern.

    Args:
        text (str): The full text of the resume.

    Returns:
        str or None: The extracted email address if found, otherwise None.
    """
    # Regex for matching standard email formats.
    email_regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    matches = re.findall(email_regex, text)
    return matches[0] if matches else None

def _extract_phone(text):
    """
    Extracts the first valid phone number found in the text using a regex pattern.
    The regex attempts to match various common phone number formats and then normalizes
    the result by removing common separators.

    Args:
        text (str): The full text of the resume.

    Returns:
        str or None: The extracted and cleaned phone number if found, otherwise None.
    """
    # Regex designed to find various phone number formats including optional country codes,
    # parentheses, spaces, hyphens, and dots as separators.
    phone_regex = r"(?:\+?\d{1,3}\s?)?(?:\(\s*\d{3}\s*\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}"
    matches = re.findall(phone_regex, text)
    if matches:
        # Clean up the found phone number by removing common non-digit characters (except '+')
        # This helps in normalizing the phone number format.
        first_match = matches[0]
        return re.sub(r'[^\d+]', '', first_match) # Keep digits and plus sign
    return None

def _extract_linkedin(text):
    """
    Extracts the first LinkedIn profile URL found in the text.
    Normalizes the URL to include "https://" and removes trailing slashes.

    Args:
        text (str): The full text of the resume.

    Returns:
        str or None: The normalized LinkedIn URL if found, otherwise None.
    """
    # Regex to find LinkedIn profile URLs, including common variations.
    linkedin_regex = r"linkedin\.com/in/[\w-]+/?|\b[\w-]+\.linkedin\.com(?:/)?[\w-]*"
    matches = re.findall(linkedin_regex, text, re.IGNORECASE)
    if matches:
        full_url = matches[0]
        if not full_url.lower().startswith("http"):
            full_url = "https://" + full_url
        # Remove trailing slash if present for consistency
        if full_url.endswith('/'):
            full_url = full_url[:-1]
        return full_url
    return None

def _extract_github(text):
    """
    Extracts the first GitHub profile URL or GitHub Pages URL found in the text.
    Normalizes the URL to include "https://" and removes trailing slashes.

    Args:
        text (str): The full text of the resume.

    Returns:
        str or None: The normalized GitHub URL if found, otherwise None.
    """
    # Regex to find GitHub profile URLs or GitHub Pages links.
    github_regex = r"github\.com/[\w.-]+/?|\b[\w-]+\.github\.io(?:/[\w.-]*)?"
    matches = re.findall(github_regex, text, re.IGNORECASE)
    if matches:
        full_url = matches[0]
        if not full_url.lower().startswith("http"):
            full_url = "https://" + full_url
        if full_url.endswith('/'):
            full_url = full_url[:-1]
        return full_url
    return None


def _extract_basic_info(text):
    """
    Orchestrates the extraction of basic contact information (name, email, phone,
    LinkedIn, GitHub) from the provided resume text using individual regex-based extractors.
    This is a simplified parser. For production, consider more advanced NLP libraries or services.

    Args:
        text (str): The full text of the resume.

    Returns:
        dict: A dictionary containing the extracted information. Keys are standardized
              (e.g., "fullName", "email") and values are the extracted strings.
              Fields not found will be omitted from the dictionary (value is None).
    """
    extracted_data = {}

    if not text or not text.strip(): # Check if text is None or empty after stripping whitespace
        return extracted_data # Return empty dict if no text content

    # Attempt to extract each piece of information.
    # The individual extraction functions handle None returns if data isn't found.
    extracted_data['fullName'] = _extract_name(text)
    extracted_data['email'] = _extract_email(text)
    extracted_data['phone'] = _extract_phone(text)
    extracted_data['linkedin'] = _extract_linkedin(text)
    extracted_data['github'] = _extract_github(text)

    # Future placeholders for more advanced parsing:
    # extracted_data['address'] = _extract_address(text)
    # extracted_data['skills'] = _extract_skills(text)
    # extracted_data['experience'] = _extract_experience_sections(text)
    # extracted_data['education'] = _extract_education_sections(text)

    # Filter out any keys where the value is None, to return a clean dictionary.
    return {k: v for k, v in extracted_data.items() if v is not None}


def parse_resume_data(resume_bytes, file_name):
    """
    Main function to parse a resume file provided as bytes.
    It determines the file type (DOCX or PDF) based on the file name's extension,
    extracts the raw text, and then attempts to extract structured information.

    Args:
        resume_bytes (bytes): The byte content of the resume file.
        file_name (str): The original name of the file (e.g., "my_resume.pdf").

    Returns:
        tuple: (parsed_info, error_message)
               - parsed_info (dict or None): A dictionary of extracted information if successful.
                 If text extraction fails critically, this can be None. If text is extracted
                 but no specific info is found, it will be an empty dict.
               - error_message (str or None): An error message string if any error occurs during
                 file processing or text extraction, otherwise None.
    """
    file_stream = io.BytesIO(resume_bytes)
    text = None
    error = None

    file_ext = file_name.split('.')[-1].lower()

    if file_ext == 'docx':
        text, error = _parse_docx(file_stream)
    elif file_ext == 'pdf':
        text, error = _parse_pdf(file_stream)
    else:
        error = f"Unsupported file type: .{file_ext}. Please use PDF or DOCX."
        return None, error

    if error:
        return None, error

    if not text or not text.strip():
        return {}, "Could not extract any text from the resume."


    # Basic information extraction
    parsed_info = _extract_basic_info(text)

    # For now, we'll also include the full text if needed by other processes,
    # though it might be large. Consider if this is always desired.
    # parsed_info['full_text'] = text

    return parsed_info, None

if __name__ == '__main__':
    # This block is for direct testing of the resume_parser.py module.
    # It allows running `python resume_parser.py` from the command line
    # to test parsing of specified local DOCX or PDF files.
    def test_file(filepath):
        """Helper function to test parsing a single file."""
        print(f"\n--- Testing: {filepath} ---")
        try:
            with open(filepath, 'rb') as f:
                file_bytes = f.read()

            data, err = parse_resume_data(file_bytes, filepath)
            if err:
                print(f"Error: {err}")
            else:
                print("Parsed Data:")
                for key, value in data.items():
                    print(f"  {key}: {value}")
        except FileNotFoundError:
            print(f"Error: Test file {filepath} not found.")
        except Exception as e:
            print(f"An unexpected error occurred during test: {e}")

    # Create dummy files for testing if you don't have them
    # (This part is for local testing, not part of the module itself)
    if not os.path.exists("dummy.pdf"):
        # This would require a library to create a PDF, e.g., reportlab
        # For now, assume manual creation or skip if not present.
        print("Skipping PDF test: dummy.pdf not found. Create one for testing.")
        pass

    if not os.path.exists("dummy.docx"):
        try:
            doc = Document()
            doc.add_paragraph("John Doe\n123-456-7890\njohn.doe@example.com\nlinkedin.com/in/johndoe\ngithub.com/johndoe\nSome text about skills and experience.")
            doc.add_paragraph("Another paragraph.")
            doc.save("dummy.docx")
            test_file("dummy.docx")
        except Exception as e:
            print(f"Could not create dummy.docx for testing: {e}")


    # To run tests:
    # 1. Make sure you have python-docx and pdfminer.six installed (pip install python-docx pdfminer.six)
    # 2. Create a dummy.pdf and/or dummy.docx in the same directory as this script,
    #    or provide paths to your own test resume files.
    # 3. Run `python resume_parser.py` from your terminal in the python_backend directory.
    # Example:
    # test_file("path/to/your/resume.pdf")
    # test_file("path/to/your/resume.docx")
