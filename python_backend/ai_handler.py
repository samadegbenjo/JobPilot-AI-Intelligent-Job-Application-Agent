"""
ai_handler.py

This module is intended to house the logic for interacting with AI services
for tasks such as:
1.  Advanced Resume Parsing: Extracting structured data (experience, education, skills)
    from resume text if the basic `resume_parser.py` is insufficient.
2.  Field Mapping Inference: Given a list of form fields extracted from a job
    application webpage, predict the correct mapping of these fields to standard
    user profile data keys (e.g., map "First Name" or "fname" to "firstName").

Currently, this module uses a **placeholder rule-based system** for field mapping
instead of actual AI calls. This allows for basic functionality and testing of the
data flow. To enable true AI capabilities, the commented-out sections for API calls
(e.g., to OpenAI, Google Gemini, Cohere) would need to be implemented, and the
user would need to provide valid API keys.
"""
import re
# import json # Would be needed for actual AI prompt construction / result parsing

# --- Placeholder for AI Client Initialization ---
# This section would contain functions to initialize clients for specific AI services.
# Example (commented out for services like OpenAI):
#
# import openai
#
# def initialize_openai_client(api_key):
#     """Initializes and returns an OpenAI client if the API key is valid."""
#     if not api_key:
#         return None, "OpenAI API key is missing."
#     try:
#         client = openai.OpenAI(api_key=api_key)
#         # Optional: Test the client with a simple call, e.g., list models
#         # client.models.list()
#         return client, None
#     except openai.AuthenticationError:
#         return None, "OpenAI API key is invalid or expired."
#     except Exception as e:
#         return None, f"Failed to initialize OpenAI client: {str(e)}"

# --- Basic Rule-Based Field Mapping (Serves as a Placeholder for AI) ---

# `BASIC_FIELD_MAPPINGS` defines common variations for standard data fields.
# This dictionary is used by the rule-based logic to guess field mappings.
# - Keys: Standardized field names (e.g., "firstName", "emailAddress").
# - Values: Lists of common labels, names, or placeholder texts found on web forms.
BASIC_FIELD_MAPPINGS = {
    "fullName": ["full name", "name", "your name", "applicant name", "legal name"],
    "firstName": ["first name", "given name", "forename", "fname", "first"],
    "lastName": ["last name", "surname", "family name", "lname", "last"],
    "email": ["email", "email address", "e-mail", "contact email", "mail"],
    "phone": ["phone", "phone number", "mobile number", "contact number", "telephone", "mobile"],
    "address": ["address", "street address", "address line 1", "mailing address", "street"],
    "city": ["city", "town", "suburb"],
    "state": ["state", "province", "region", "county"],
    "zipCode": ["zip code", "postal code", "zip", "postcode", "postal"],
    "country": ["country", "nation"],
    "linkedin": ["linkedin", "linkedin profile", "linkedin url"],
    "github": ["github", "github profile", "github url", "gh profile"],
    "portfolio": ["portfolio", "website", "personal website", "portfolio url", "web page"],
    "coverLetter": ["cover letter", "additional information", "summary", "message", "notes", "tell us more", "why you"],
    "company": ["company", "company name", "current company", "employer", "organization"],
    "jobTitle": ["job title", "title", "current role", "position", "role"],
    # Add more mappings as needed for common job application fields
}

def _normalize_label(label_text):
    """
    Normalizes a label string for more effective rule-based matching.
    Converts to lowercase, removes most punctuation (keeps hyphens), and strips whitespace.

    Args:
        label_text (str): The label text to normalize.

    Returns:
        str: The normalized label text.
    """
    if not label_text:
        return ""
    text = label_text.lower()
    # Remove punctuation except hyphens (often part of words like "e-mail" or "full-time")
    # and underscores (sometimes used in field names/ids).
    text = re.sub(r'[^\w\s\-_]', '', text) # Keep word chars, whitespace, hyphen, underscore
    text = text.strip()
    return text

def _find_mapping_rule_based(field_info):
    """
    Attempts to map a single form field (`field_info`) to a standardized key
    using the `BASIC_FIELD_MAPPINGS` rules. It checks the field's label, name,
    ID, and placeholder against known variations.

    Args:
        field_info (dict): A dictionary describing the form field, containing keys like
                           'label', 'name', 'id', 'placeholder'.

    Returns:
        str or None: The standardized field key (e.g., "firstName") if a match is found,
                     otherwise None.
    """
    # Gather all relevant text attributes from the field for matching.
    # Normalizing them increases the chance of a match.
    texts_to_check = [
        _normalize_label(field_info.get('labelText', '')), # From <label> tag
        _normalize_label(field_info.get('name', '')),      # From 'name' attribute
        _normalize_label(field_info.get('id', '')),        # From 'id' attribute
        _normalize_label(field_info.get('placeholder', '')),# From 'placeholder' attribute
        _normalize_label(field_info.get('ariaLabel', ''))  # From 'aria-label' attribute
    ]
    # Filter out any empty strings that result from missing attributes.
    texts_to_check = [text for text in texts_to_check if text]

    # Iterate through our predefined standard keys and their common variations.
    for standard_key, variations in BASIC_FIELD_MAPPINGS.items():
        for variation_keyword in variations:
            normalized_variation = _normalize_label(variation_keyword)
            for text_from_field in texts_to_check:
                # Prioritize exact matches of normalized texts.
                if normalized_variation == text_from_field:
                    return standard_key
                # Also allow matches if the keyword is a significant part of the field's text,
                # but be careful with very short keywords to avoid false positives.
                if len(normalized_variation) >= 3 and normalized_variation in text_from_field:
                    return standard_key
                # Could add more sophisticated partial matching here if needed (e.g., Levenshtein distance)
    return None


def infer_form_fields_with_ai(fields, api_key=None):
    """
    Main function to infer mappings for a list of form fields.
    **Currently, this function uses a rule-based placeholder (`_find_mapping_rule_based`)
    instead of making actual calls to an AI service.**

    The intended AI-driven process would be:
    1. Initialize an AI client using the provided `api_key`.
    2. Construct a detailed prompt containing the extracted `fields` data and instructions
       for mapping them to a predefined schema of user profile information.
    3. Send the prompt to the AI service.
    4. Parse the AI's JSON response to get the field mappings.

    Args:
        fields (list): A list of dictionaries, where each dictionary describes a form field
                       extracted by the content script (e.g., containing 'id', 'name', 'labelText', etc.).
        api_key (str, optional): The user's API key for the AI service. This is not used
                                 by the current rule-based placeholder but would be crucial for
                                 actual AI integration.

    Returns:
        tuple: (mapped_fields, error_message)
               - mapped_fields (dict): A dictionary where keys are standardized field names
                                     (e.g., "firstName") and values are the corresponding
                                     page field identifiers (e.g., 'id' or 'tempId' of the input element)
                                     that the content script should use for filling.
                                     Example: {"firstName": "page_field_id_123", "email": "user_email_on_page"}
               - error_message (str or None): An error message if something significant went wrong.
                                             For the placeholder, this is usually None.
    """
    app_logger = None
    try:
        from flask import current_app # Optional: for logging if running within a Flask app context
        app_logger = current_app.logger
        if app_logger: app_logger.info(f"AI Handler received {len(fields)} fields for inference. API key provided: {'Yes' if api_key else 'No'}")
    except RuntimeError: # Not in Flask app context (e.g. direct script run)
        print(f"AI Handler received {len(fields)} fields for inference. API key provided: {'Yes' if api_key else 'No'}")


    # --- BEGIN ACTUAL AI INTEGRATION (Commented Out Placeholder) ---
    # The following section outlines how real AI integration would look.
    # It's currently bypassed in favor of the rule-based approach below.

    # Step 1: Initialize AI Client (e.g., OpenAI, Gemini, Cohere)
    # This would typically involve using the `api_key` provided by the user.
    # Example for OpenAI:
    # ai_client, init_error = initialize_openai_client(api_key)
    # if init_error:
    #     log_message = f"AI Client Initialization Error: {init_error}"
    #     if app_logger: app_logger.error(log_message)
    #     else: print(log_message)
    #     return None, init_error # Return error if client can't be initialized
    #
    # if not ai_client: # Should be caught by init_error, but as a safeguard
    #     fallback_msg = "AI client not available. Falling back to rule-based mapping."
    #     if app_logger: app_logger.warning(fallback_msg)
    #     else: print(fallback_msg)
    #     # Fallback to rule-based implemented below
    # else:
    #     # Step 2: Construct a detailed prompt for the AI
    #     # The prompt should describe the task, provide the extracted form fields (as JSON),
    #     # list the target standardized keys (e.g., "firstName", "email"), and specify
    #     # the desired JSON output format for the mappings.
    #     prompt = f"""
    #     Analyze the following HTML form fields extracted from a job application page:
    #     {json.dumps(fields, indent=2)}
    #
    #     Your task is to map these fields to the following standard user profile keys:
    #     {json.dumps(list(BASIC_FIELD_MAPPINGS.keys()), indent=2)}
    #
    #     Return a JSON object where each key is a standard user profile key (e.g., "firstName")
    #     and its value is the 'tempId' (preferred) or 'id' or 'name' of the corresponding input field from the page.
    #     If a field cannot be confidently mapped, omit it from the result.
    #     Example output: {{ "email": "field_temp_id_2", "lastName": "input_lname" }}
    #     """
    #
    #     # Step 3: Make the API Call to the AI service
    #     try:
    #         # Example using OpenAI's chat completions:
    #         # response = ai_client.chat.completions.create(
    #         #     model="gpt-3.5-turbo", # Or a more advanced model like gpt-4
    #         #     messages=[{"role": "system", "content": "You are an expert in web form field mapping."},
    #         #               {"role": "user", "content": prompt}],
    #         #     response_format={"type": "json_object"} # For models that support JSON mode
    #         # )
    #         # ai_result_str = response.choices[0].message.content
    #         # mapped_fields_from_ai = json.loads(ai_result_str) # Parse the JSON string from AI
    #
    #         # log_message = f"AI mapping successful: {mapped_fields_from_ai}"
    #         # if app_logger: app_logger.info(log_message)
    #         # else: print(log_message)
    #         # return mapped_fields_from_ai, None # Return the AI's mapping
    #
    #     except Exception as e:
    #         error_msg = f"AI API call or processing failed: {str(e)}. Falling back to rule-based."
    #         if app_logger: app_logger.error(error_msg)
    #         else: print(error_msg)
    #         # Fallback to rule-based implemented below
    #
    # --- END ACTUAL AI INTEGRATION (Commented Out Placeholder) ---


    # --- Current: Rule-Based Fallback/Placeholder Implementation ---
    # This logic is used if AI integration is not enabled or fails.
    if app_logger: app_logger.info("Using rule-based mapping as AI placeholder/fallback.")
    else: print("Using rule-based mapping as AI placeholder/fallback.")

    inferred_mappings = {} # Stores {standard_key: page_field_identifier}
    unmapped_fields_details = [] # For logging fields that couldn't be mapped

    for field_obj in fields:
        # The `field_obj` is expected to have 'tempId' (generated by content.js if no id),
        # 'id', 'name', 'labelText', 'placeholder', 'ariaLabel'.
        # The 'tempId' is the preferred identifier to ensure uniqueness if original 'id' is missing or duplicated.
        page_field_identifier = field_obj.get('tempId') or field_obj.get('id') or field_obj.get('name')

        if not page_field_identifier:
            # This field is problematic as it lacks a reliable identifier.
            # Log it and skip, as we can't reliably target it for filling.
            unmapped_fields_details.append(field_obj)
            if app_logger: app_logger.warning(f"Skipping field due to missing identifier: {field_obj}")
            else: print(f"Skipping field due to missing identifier: {field_obj}")
            continue

        # Use the rule-based function to find a mapping.
        standardized_key = _find_mapping_rule_based(field_obj)

        if standardized_key:
            # If this standard key (e.g., "email") is already mapped to a field,
            # the current simple rule-based logic will take the first one it encounters.
            # An AI could potentially handle multiple inputs for one concept or rank them.
            if standardized_key not in inferred_mappings:
                inferred_mappings[standardized_key] = page_field_identifier
            else:
                # Log that a potential conflict or duplicate mapping occurred.
                log_msg_conflict = (f"Rule-based: Standard key '{standardized_key}' already mapped to "
                                    f"'{inferred_mappings[standardized_key]}'. Ignoring new candidate "
                                    f"'{page_field_identifier}' for field: {field_obj.get('labelText') or field_obj.get('name')}.")
                if app_logger: app_logger.warning(log_msg_conflict)
                else: print(log_msg_conflict)
        else:
            # This field was not mapped by the rule-based system.
            unmapped_fields_details.append(field_obj)

    # Logging the outcome of the rule-based mapping.
    num_mapped = len(inferred_mappings)
    num_unmapped = len(unmapped_fields_details)
    log_summary = f"Rule-based mapping complete. Mapped: {num_mapped} fields, Unmapped: {num_unmapped} fields."
    if app_logger:
        app_logger.info(log_summary)
        if num_unmapped > 0:
            app_logger.debug(f"Unmapped fields details: {unmapped_fields_details}")
    else:
        print(log_summary)
        if num_unmapped > 0:
            print(f"Unmapped fields details: {unmapped_fields_details}")

    # The function returns the dictionary of inferred mappings.
    # The content script will use this: e.g., for "firstName", fill the element with id/tempId stored here.
    return inferred_mappings, None


if __name__ == '__main__':
    # This block allows for direct testing of the ai_handler.py module.
    # You can run `python ai_handler.py` from the terminal within the `python_backend` directory.
    # It simulates providing a list of extracted form fields (as `sample_fields_from_content_script`)
    # and then prints the mappings inferred by the current rule-based logic.
    # The `sample_fields_from_content_script` should mirror the structure produced by
    # `extractFormFields` in `js/content.js`, including `labelText`, `tempId`, etc.
    print("--- Testing AI Handler (Rule-Based Placeholder) ---")
    sample_fields_from_content_script = [
        {"tempId": "f0", "id": "fname", "name": "firstName", "type": "text", "labelText": "First Name", "placeholder": "", "ariaLabel": None, "value": "", "tagName": "input"},
        {"tempId": "f1", "id": "lname", "name": "lastName", "type": "text", "labelText": "Last Name", "placeholder": "", "ariaLabel": None, "value": "", "tagName": "input"},
        {"tempId": "f2", "id": "email_field", "name": "email", "type": "email", "labelText": "Your Email Address", "placeholder": "user@example.com", "ariaLabel": None, "value": "", "tagName": "input"},
        {"tempId": "f3", "id": "phone_number", "name": "phone", "type": "tel", "labelText": "Contact Phone", "placeholder": "", "ariaLabel": None, "value": "", "tagName": "input"},
        {"tempId": "f4", "id": "applicant_notes", "name": "notes", "type": "textarea", "labelText": "Additional Notes or Cover Letter", "placeholder": "", "ariaLabel": None, "value": "", "tagName": "textarea"},
        {"tempId": "f5", "id": "company_field", "name": "company", "type": "text", "labelText": "Company Inc.", "placeholder": "Current Company", "ariaLabel": None, "value": "", "tagName": "input"},
        {"tempId": "f6", "id": "random_field_123", "name": "custom1", "type": "text", "labelText": "Your favorite color", "placeholder": "", "ariaLabel": None, "value": "", "tagName": "input"},
        {"tempId": "f7", "id": None, "name": "user_github_url", "type": "url", "labelText": "GitHub Profile", "placeholder": "https://github.com/username", "ariaLabel": None, "value": "", "tagName": "input"},
    ]

    print("\nInput Fields (simulated from content script):")
    for i, field in enumerate(sample_fields_from_content_script):
        print(f"  Field {i}: {field}")

    # Test with the sample fields
    # The api_key is included as it's part of the function signature, though not used by the placeholder.
    mapped_data, error = infer_form_fields_with_ai(
        sample_fields_from_content_script,
        api_key="dummy_api_key_for_testing_signature"
    )

    if error:
        print(f"\nError during inference: {error}")
    else:
        print("\nInferred Mappings (Standardized Key -> Page Field tempId/ID/Name):")
        if mapped_data:
            for standard_key, page_field_identifier in mapped_data.items():
                print(f"  '{standard_key}': '{page_field_identifier}'")
        else:
            print("  No mappings were inferred by the rule-based system.")

    print("\n--- Test with a more ambiguous field ---")
    ambiguous_field_test = [
         {"tempId": "af1", "id": "userFullname", "name": "userFullname", "type": "text", "labelText": "Enter your full name here", "placeholder": "e.g. Jane Doe", "ariaLabel": "Full legal name", "value": "", "tagName": "input"},
    ]
    print("\nInput Field for ambiguous test:")
    print(f"  Field 0: {ambiguous_field_test[0]}")

    mapped_data_ambiguous, error_ambiguous = infer_form_fields_with_ai(ambiguous_field_test)

    if error_ambiguous:
        print(f"\nError during ambiguous field inference: {error_ambiguous}")
    else:
        print("\nInferred Mappings for ambiguous field (Standardized Key -> Page Field tempId/ID/Name):")
        if mapped_data_ambiguous:
            for standard_key, page_field_identifier in mapped_data_ambiguous.items():
                print(f"  '{standard_key}': '{page_field_identifier}'")
        else:
            print("  No mappings were inferred for the ambiguous field by the rule-based system.")
