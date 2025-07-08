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
and has commented-out stubs for actual AI calls. To enable true AI capabilities,
the API call sections would need to be implemented, and the user would need to
provide valid API keys via the extension popup.
"""
import re
import json # Needed for constructing JSON prompts or parsing JSON responses

# AI SDKs - Import with fallbacks if not installed, allowing rule-based to always work.
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    openai = None
    OPENAI_AVAILABLE = False
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GEMINI_AVAILABLE = False
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None
    ANTHROPIC_AVAILABLE = False


# --- AI Client Initialization Functions ---

def initialize_openai_client(api_key):
    """
    Initializes and returns an OpenAI client.

    Args:
        api_key (str): The OpenAI API key.

    Returns:
        tuple: (client, error_message)
               - client: OpenAI client instance if successful.
               - error_message (str or None): Error message if initialization fails.
    """
    if not OPENAI_AVAILABLE:
        return None, "OpenAI library is not installed. Please install it via 'pip install openai'."
    if not api_key:
        return None, "OpenAI API key is missing."
    try:
        client = openai.OpenAI(api_key=api_key)
        # A lightweight way to test client validity might be client.models.list(), but adds a network call.
        # For now, assume key is valid if client initializes without immediate error.
        return client, None
    except openai.AuthenticationError: # Specific error for bad keys
        return None, "OpenAI API key is invalid or expired."
    except Exception as e: # Catch other potential errors during client init
        return None, f"Failed to initialize OpenAI client: {str(e)}"

def initialize_gemini_client(api_key):
    """
    Configures the Google Gemini (genai) client.

    Args:
        api_key (str): The Google Gemini API key.

    Returns:
        tuple: (client_module, error_message)
               - client_module: The configured `genai` module if successful.
               - error_message (str or None): Error message if configuration fails.
    """
    if not GEMINI_AVAILABLE:
        return None, "Google Generative AI library not installed. Install via 'pip install google-generativeai'."
    if not api_key:
        return None, "Google Gemini API key is missing."
    try:
        genai.configure(api_key=api_key)
        # Gemini's genai.configure doesn't typically raise auth errors immediately.
        # Errors often occur on the first actual API call.
        # We return the module itself as a sign of successful configuration.
        return genai, None
    except Exception as e:
        return None, f"Failed to configure Google Gemini client: {str(e)}. Key might be invalid or quotas exceeded."

def initialize_claude_client(api_key):
    """
    Initializes and returns an Anthropic Claude client.

    Args:
        api_key (str): The Anthropic Claude API key.

    Returns:
        tuple: (client, error_message)
               - client: Anthropic client instance if successful.
               - error_message (str or None): Error message if initialization fails.
    """
    if not ANTHROPIC_AVAILABLE:
        return None, "Anthropic library not installed. Install via 'pip install anthropic'."
    if not api_key:
        return None, "Anthropic Claude API key is missing."
    try:
        client = anthropic.Anthropic(api_key=api_key)
        # Similar to OpenAI, a lightweight test call could be added if desired.
        return client, None
    except anthropic.APIConnectionError: # More specific error for connection issues.
         return None, "Could not connect to Anthropic API. Check network or API status."
    except anthropic.AuthenticationError: # Specific error for bad keys.
        return None, "Anthropic Claude API key is invalid."
    except Exception as e:
        return None, f"Failed to initialize Anthropic Claude client: {str(e)}"


# --- Basic Rule-Based Field Mapping (Serves as a Placeholder/Fallback for AI) ---

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


def infer_form_fields_with_ai(fields, user_data_context, selected_provider="rule_based", api_key=None):
    """
    Infers mappings for a list of webpage form fields to standardized user data keys.

    This function orchestrates the field mapping process. It attempts to use a specified
    AI provider (OpenAI, Gemini, Claude) if selected by the user and a valid API key is provided.
    If an AI provider is chosen, it initializes the respective client, constructs a prompt
    with the form field data and user data context, and (in a full implementation) would
    make an API call to the AI service to get field mappings.

    Currently, the actual AI API calls are placeholder sections. If an AI provider is selected
    but the call is not implemented or fails, or if "rule_based" is selected, the function
    falls back to the `_find_mapping_rule_based` method.

    Args:
        fields (list of dict): Data for each extracted form field from the webpage.
            Each dict contains keys like 'tempId', 'id', 'name', 'labelText', 'type', etc.
        user_data_context (dict): Comprehensive user data (profile, resume, employment Qs)
            to provide context for AI-driven mapping.
        selected_provider (str, optional): Identifier for the chosen AI service
            (e.g., "openai", "gemini", "claude"). Defaults to "rule_based".
        api_key (str, optional): The API key for the selected AI provider.
            Required if `selected_provider` is not "rule_based".

    Returns:
        tuple: (mapped_fields, error_message)
            - mapped_fields (dict): A dictionary where keys are standardized user data keys
              (e.g., "firstName") and values are the 'tempId' (or 'id'/'name') of the
              corresponding webpage form field. Example: `{"email": "tempId_123"}`.
            - error_message (str or None): A string containing an error message if a
              significant issue occurred (e.g., client init failure for chosen provider if not falling back),
              otherwise None. For rule-based or successful placeholder AI, this is usually None.
    """
    app_logger = None
    try:
        from flask import current_app
        app_logger = current_app.logger
        log_func = app_logger.info if app_logger else print
    except RuntimeError: # Not in Flask app context
        log_func = print

    log_func(f"Inferring fields using provider: {selected_provider}. API key provided: {'Yes' if api_key else 'No'}.")
    log_func(f"Number of fields to map: {len(fields)}. User data context keys: {list(user_data_context.keys()) if user_data_context else 'None'}")


    ai_client = None
    init_error = None

    if selected_provider == "openai":
        ai_client, init_error = initialize_openai_client(api_key)
    elif selected_provider == "gemini":
        ai_client, init_error = initialize_gemini_client(api_key)
    elif selected_provider == "claude":
        ai_client, init_error = initialize_claude_client(api_key)
    elif selected_provider != "rule_based":
        init_error = f"Unknown AI provider: {selected_provider}. Falling back to rule-based."

    if init_error:
        log_func(f"AI Client Initialization Error for {selected_provider}: {init_error}")
        # Fallback to rule-based if specific AI provider fails or is unknown
        selected_provider = "rule_based"
        log_func("Falling back to rule_based due to client initialization error.")


    if selected_provider != "rule_based" and ai_client:
        # --- Actual AI Call Section (Placeholder for now) ---
        log_func(f"Attempting to use AI provider: {selected_provider}")

        # Step 2: Construct a prompt for the AI
        # This is a generic prompt and would need significant refinement for each AI model.
        # It should include the extracted `fields`, the `user_data_context` keys (or relevant values),
        # and clear instructions on the desired JSON output format for mappings.

        # Create a simplified list of user data keys they can map to.
        available_user_data_keys = list(user_data_context.keys() if user_data_context else [])

        prompt_fields_json = json.dumps(fields, indent=2)
        prompt_user_keys_json = json.dumps(available_user_data_keys, indent=2)

        prompt = f"""
        You are an expert AI assistant that maps HTML form fields from job applications
        to a predefined set of user data keys.

        Here are the HTML form fields extracted from a webpage:
        {prompt_fields_json}

        Here are the available user data keys you should try to map the fields to:
        {prompt_user_keys_json}

        Based on the field information (labelText, name, id, placeholder, ariaLabel, type, tagName),
        provide a JSON object where each key is one of the available user data keys,
        and its value is the 'tempId' (preferred, if available) or 'id' or 'name' of the
        corresponding input field from the webpage.

        Prioritize strong semantic matches. If a field cannot be confidently mapped, omit it.
        Example output: {{ "email": "field_temp_id_2", "lastName": "input_lname", "visaStatus": "f_visa_sponsorship" }}
        """
        log_func(f"Generated prompt for {selected_provider} (first 300 chars): {prompt[:300]}...")

        try:
            # This is where you would make the actual API call
            # For example, with OpenAI:
            # if selected_provider == "openai" and openai:
            #     response = ai_client.chat.completions.create(
            #         model="gpt-3.5-turbo", # Or a more advanced model
            #         messages=[
            #             {"role": "system", "content": "You are an expert in web form field mapping."},
            #             {"role": "user", "content": prompt}
            #         ],
            #         response_format={"type": "json_object"} # If supported
            #     )
            #     ai_result_str = response.choices[0].message.content
            #     mapped_fields_from_ai = json.loads(ai_result_str)
            #     log_func(f"AI mapping successful from {selected_provider}: {mapped_fields_from_ai}")
            #     return mapped_fields_from_ai, None

            # Similar blocks for Gemini and Claude would go here.
            # For now, we'll simulate an AI failure to fall back to rule-based.
            log_func(f"AI call to {selected_provider} is currently a placeholder. Falling back to rule-based.")
            raise NotImplementedError(f"Actual AI call for {selected_provider} not implemented yet.")

        except NotImplementedError as nie: # Catching our specific placeholder exception
             log_func(str(nie))
             # Fall through to rule-based below
        except Exception as e:
            log_func(f"AI API call or processing failed for {selected_provider}: {str(e)}. Falling back to rule-based.")
            # Fall through to rule-based below

    # --- Rule-Based Fallback/Placeholder Implementation ---
    # This logic is used if AI is not selected, client init fails, or AI call fails.
    log_func("Using rule-based mapping.")

    inferred_mappings = {}
    unmapped_fields_details = []

    for field_obj in fields:
        page_field_identifier = field_obj.get('tempId') or field_obj.get('id') or field_obj.get('name')

        if not page_field_identifier:
            unmapped_fields_details.append(field_obj)
            log_func(f"Skipping field due to missing identifier: {field_obj}")
            continue

        standardized_key = _find_mapping_rule_based(field_obj)

        if standardized_key:
            if standardized_key not in inferred_mappings:
                inferred_mappings[standardized_key] = page_field_identifier
            else:
                log_msg_conflict = (f"Rule-based: Standard key '{standardized_key}' already mapped to "
                                    f"'{inferred_mappings[standardized_key]}'. Ignoring new candidate "
                                    f"'{page_field_identifier}' for field: {field_obj.get('labelText') or field_obj.get('name')}.")
                log_func(log_msg_conflict)
        else:
            unmapped_fields_details.append(field_obj)

    num_mapped = len(inferred_mappings)
    num_unmapped = len(unmapped_fields_details)
    log_summary = f"Rule-based mapping complete. Mapped: {num_mapped} fields, Unmapped: {num_unmapped} fields."
    log_func(log_summary)
    if num_unmapped > 0 and app_logger: # Only log details if Flask logger is available
        app_logger.debug(f"Unmapped fields details (rule-based): {unmapped_fields_details}")
    elif num_unmapped > 0:
         print(f"Unmapped fields details (rule-based): {unmapped_fields_details}")

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
