import base64
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

# Import placeholder modules (will be created in later steps)
from resume_parser import parse_resume_data
from ai_handler import infer_form_fields_with_ai

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes, allowing requests from the extension

# Ensure upload directory exists (if saving files, not strictly needed for base64 processing, but good practice if temp files were used)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    """
    Root endpoint to check if the backend server is running.
    Returns:
        JSON: A simple message indicating the server is alive.
    """
    return jsonify({"message": "Job Application Assistant Python Backend is running!"})

@app.route('/parse_resume', methods=['POST'])
def handle_parse_resume():
    """
    Endpoint to receive resume file content (base64 encoded) and its file name,
    then parse it to extract information.

    Expects JSON in request body:
    {
        "file_content_base64": "<base64_encoded_string_of_file_content>",
        "file_name": "<original_file_name.ext>"
    }

    Returns:
        JSON: On success (200), {"message": "Resume parsed successfully", "parsed_data": {extracted_info}}.
              On error (400, 500), {"error": "<error_description>"}.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        file_content_base64 = data.get('file_content_base64')
        file_name = data.get('file_name')

        if not file_content_base64 or not file_name:
            return jsonify({"error": "Missing file_content_base64 or file_name"}), 400

        # Decode the base64 string to bytes
        try:
            resume_bytes = base64.b64decode(file_content_base64)
        except Exception as e:
            app.logger.error(f"Base64 decoding failed: {e}")
            return jsonify({"error": f"Invalid base64 content: {e}"}), 400

        # Call the resume parsing logic (from resume_parser.py)
        # This function should handle different file types based on file_name or content analysis
        parsed_data, error = parse_resume_data(resume_bytes, file_name)

        if error:
            app.logger.error(f"Error parsing resume {file_name}: {error}")
            return jsonify({"error": error}), 500

        app.logger.info(f"Successfully parsed resume: {file_name}")
        return jsonify({"message": "Resume parsed successfully", "parsed_data": parsed_data}), 200

    except Exception as e:
        app.logger.error(f"Error in /parse_resume: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/infer_fields', methods=['POST'])
def handle_infer_fields():
    """
    Endpoint to receive extracted form fields from a webpage and (eventually) use AI
    to suggest mappings to standardized user profile keys. Currently uses rule-based logic.

    Expects JSON in request body:
    {
        "fields": [
            {"id": "...", "name": "...", "type": "...", "label": "...", ...},
            ...
        ],
        "api_key": "<user_provided_ai_service_api_key>" (optional)
    }

    Returns:
        JSON: On success (200), {"message": "Fields inferred successfully", "mapped_fields": {standard_key: page_field_id}}.
              On error (400, 500), {"error": "<error_description>"}.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        fields = data.get('fields')
        api_key = data.get('api_key') # User's API key for an AI service

        if not fields:
            return jsonify({"error": "Missing 'fields' data"}), 400

        # Call the AI handler logic (from ai_handler.py)
        # This function would interact with an AI service
        mapped_fields, error = infer_form_fields_with_ai(fields, api_key)

        if error:
            app.logger.error(f"Error in AI inference: {error}")
            return jsonify({"error": error}), 500

        app.logger.info("Successfully inferred field mappings.")
        return jsonify({"message": "Fields inferred successfully", "mapped_fields": mapped_fields}), 200

    except Exception as e:
        app.logger.error(f"Error in /infer_fields: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    # This block allows running the Flask development server directly.
    # Command: python app.py
    # Environment variables like FLASK_ENV=development (or FLASK_DEBUG=1) can be set for debug mode.
    # For production, a more robust WSGI server like Gunicorn or Waitress should be used,
    # e.g., gunicorn -w 4 -b 127.0.0.1:5000 app:app
    app.run(debug=True, port=5000) # Runs on http://127.0.0.1:5000/
