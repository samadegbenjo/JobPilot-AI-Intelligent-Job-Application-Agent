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

    This function orchestrates the field mapping process.
    If "openai" is the `selected_provider` and a valid API key is provided and the
    OpenAI client initializes successfully, this function:
    1. Constructs a detailed prompt for an OpenAI Chat Completions model (e.g., gpt-3.5-turbo).
       The prompt includes the extracted webpage form fields and the available user data keys.
    2. Makes an API call to OpenAI, requesting a JSON object as output.
    3. Parses the AI's JSON response to get the field mappings.
    4. If the OpenAI call or JSON parsing fails, it logs the error and falls back to the
       rule-based mapping system.

    For other AI providers ("gemini", "claude"), it currently logs that the implementation
    is pending and defaults to rule-based mapping.
    If "rule_based" is selected, or if any AI provider path fails before returning a
    mapping, it uses the `_find_mapping_rule_based` method.

    Args:
        fields (list of dict): Data for each extracted form field from the webpage.
            Each dict contains keys like 'tempId', 'id', 'name', 'labelText', 'type', etc.
        user_data_context (dict): Comprehensive user data (profile, resume, employment Qs)
            to provide context for AI-driven mapping.
        selected_provider (str, optional): Identifier for the chosen AI service
            (e.g., "openai", "gemini", "claude"). Defaults to "rule_based".
        api_key (str, optional): The API key for the selected AI provider.
            Required if `selected_provider` is an AI model and not "rule_based".

    Returns:
        tuple: (mapped_fields, error_message)
            - mapped_fields (dict): A dictionary where keys are standardized user data keys
              (e.g., "firstName") and values are the 'tempId' (or 'id'/'name') of the
              corresponding webpage form field. Example: `{"email": "tempId_123"}`.
              This can be an empty dict `{}` if no confident mappings are found.
            - error_message (str or None): Currently, this function aims to always return a mapping
              (even if empty or rule-based) and logs errors internally. So, `error_message`
              is typically `None` from this function's direct return. Errors from `app.py`
              might still occur for request-level issues.
    """
    app_logger = None
    try:
        from flask import current_app
        app_logger = current_app.logger
        # Use specific logger levels if app_logger is available
        log_info = app_logger.info if app_logger else print
        log_warning = app_logger.warning if app_logger else print
        log_error = app_logger.error if app_logger else print
        log_debug = app_logger.debug if app_logger else print # For more verbose logs
    except RuntimeError: # Not in Flask app context
        log_info = print
        log_warning = print
        log_error = print
        log_debug = print

    log_info(f"--- infer_form_fields_with_ai ---")
    log_info(f"Selected provider: {selected_provider}")
    log_info(f"API key provided: {'Yes' if api_key else 'No'}")
    log_info(f"Number of fields received: {len(fields)}")
    if user_data_context:
        log_debug(f"User data context keys: {list(user_data_context.keys())}")
    else:
        log_info("User data context: None")
    log_debug(f"Received fields for mapping: {json.dumps(fields, indent=2)}")


    openai_client_instance = None # Will hold the initialized OpenAI client
    # This variable will determine if we attempt an AI call or default to rule-based.
    # It's set if a provider is chosen, library available, key provided, and client inits.
    attempt_ai_call_for_provider = None
    # Will hold the initialized client if successful for the target provider
    initialized_ai_client = None

    if selected_provider == "openai":
        if not OPENAI_AVAILABLE:
            log_warning("OpenAI provider selected, but the 'openai' library is not installed. Falling back to rule-based.")
        elif not api_key:
            log_warning("OpenAI provider selected, but no API key was provided. Falling back to rule-based.")
        else:
            client, init_error = initialize_openai_client(api_key)
            if init_error:
                log_error(f"OpenAI client initialization failed: {init_error}. Falling back to rule-based.")
            elif client:
                log_info("OpenAI client initialized successfully.")
                initialized_ai_client = client
                attempt_ai_call_for_provider = "openai"
            else:
                log_warning("OpenAI client initialization returned no client and no specific error. Falling back to rule-based.")

    elif selected_provider == "gemini":
        # Similar logic for Gemini if it were being implemented now
        if not GEMINI_AVAILABLE:
            log_warning(f"Gemini provider selected, but 'google-generativeai' library not installed. Falling back to rule-based.")
        # elif not api_key: ...
        else:
            # client, init_error = initialize_gemini_client(api_key) ...
            log_info(f"'{selected_provider}' AI provider selected. Full API call implementation pending. Falling back to rule-based.")
        # Force fallback for non-OpenAI providers in this focused step
        attempt_ai_call_for_provider = None # Ensure it falls to rule-based
    elif selected_provider == "claude":
        if not ANTHROPIC_AVAILABLE:
            log_warning(f"Claude provider selected, but 'anthropic' library not installed. Falling back to rule-based.")
        # elif not api_key: ...
        else:
            log_info(f"'{selected_provider}' AI provider selected. Full API call implementation pending. Falling back to rule-based.")
        attempt_ai_call_for_provider = None # Ensure it falls to rule-based
    elif selected_provider != "rule_based":
        log_warning(f"Unknown AI provider: '{selected_provider}'. Falling back to rule-based.")
        attempt_ai_call_for_provider = None # Ensure it falls to rule-based

    # Decision point: Attempt AI call or use rule-based
    if attempt_ai_call_for_provider == "openai" and initialized_ai_client:
        # --- OpenAI API Call Section ---
        log_info(f"Attempting field mapping with OpenAI provider.")

        # Construct the prompt for OpenAI.
        # This involves preparing the extracted field data and user context keys in a format
        # that the AI can easily understand and process.
        prompt_fields_details = []
        for f_idx, f_val in enumerate(fields): # Using enumerate to get an index for more robust temp ref if needed
            field_ref = f_val.get('tempId') or f_val.get('id') or f_val.get('name') or f"unknown_field_{f_idx}"
            field_detail = {
                "field_ref": field_ref,
                "label": f_val.get('labelText'),
                "name_attr": f_val.get('name'),
                "id_attr": f_val.get('id'),
                "placeholder": f_val.get('placeholder'),
                "aria_label": f_val.get('ariaLabel'),
                "type": f_val.get('type'),
                "tag": f_val.get('tagName')
            }
            prompt_fields_details.append({k: v for k, v in field_detail.items() if v is not None})
        prompt_fields_json = json.dumps(prompt_fields_details, indent=2)

        available_user_data_keys = sorted(list(user_data_context.keys() if user_data_context else []))
        prompt_user_keys_json = json.dumps(available_user_data_keys, indent=2)

        system_message = """You are an expert AI assistant specializing in web form field mapping for job applications.
Your task is to analyze a list of HTML form fields extracted from a job application webpage and map them to a predefined set of standardized user data keys.
The goal is to identify which webpage field corresponds to each piece of user information.
You MUST output a valid JSON object, and nothing else.
"""
        user_prompt = f"""
Analyze the following HTML form fields extracted from a webpage:
```json
{prompt_fields_json}
```

Your goal is to map these webpage fields to the most appropriate keys from the following list of available user data keys:
```json
{prompt_user_keys_json}
```

Mapping Instructions:
1.  For each user data key from the "available user data keys" list, determine if there is a corresponding field in the "HTML form fields" list.
2.  The "field_ref" value from the "HTML form fields" list is the identifier you MUST use for the webpage field in your mapping output.
3.  Base your mapping on semantic similarity of the field's `label`, `name_attr`, `id_attr`, `placeholder`, `aria_label`, `type`, and `tag`.
4.  Consider common variations (e.g., "First Name", "fname", "given_name" on a webpage could all map to a standard user data key like "firstName" if "firstName" is in the "available user data keys" list).
5.  If a user data key clearly matches a webpage field, include that user data key in your output JSON object, with its value being the "field_ref" of the matched webpage field.
6.  CRITICAL: If a user data key does not have a clear and confident corresponding field on the webpage, DO NOT include that user data key in your output JSON. Only return confident mappings.
7.  The output MUST be a single, valid JSON object. Do not include any explanations, apologies, or conversational text before or after the JSON object.

Example of desired JSON output format (if "fullName", "email", and "visaStatus" were mappable user data keys):
{{
  "fullName": "some_field_ref_abc",
  "email": "field_temp_id_123",
  "visaStatus": "visa_dropdown_ref_xyz"
}}

If no fields can be confidently mapped, return an empty JSON object: {{}}

Now, provide the JSON object for the given fields and user data keys.
"""
        log_debug(f"System Message for OpenAI: {system_message}") # Log full system message at debug
        log_info(f"Constructed OpenAI User Prompt (length: {len(user_prompt)} chars). First 300: {user_prompt[:300]}...")
        log_debug(f"Full OpenAI User Prompt: {user_prompt}")

        ai_result_str = "" # Initialize for potential use in error logging if API response is malformed
        try:
            # Make the actual API call to OpenAI
            log_info(f"Attempting OpenAI API call with model 'gpt-3.5-turbo'...")
            response = initialized_ai_client.chat.completions.create(
                model="gpt-3.5-turbo", # Or a more advanced model like "gpt-4-turbo" if available/needed
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}, # Request JSON output
                temperature=0.2 # Lower temperature for more deterministic, less creative output
            )
            ai_result_str = response.choices[0].message.content
            log_debug(f"Raw response string from OpenAI: {ai_result_str}")

            # Parse the JSON string response from the AI
            mapped_fields_from_ai = json.loads(ai_result_str)
            log_info(f"Successfully parsed OpenAI response. Found {len(mapped_fields_from_ai)} mappings.")
            log_debug(f"OpenAI Mapped Fields: {json.dumps(mapped_fields_from_ai, indent=2)}")
            return mapped_fields_from_ai, None # Return successful AI mapping

        except json.JSONDecodeError as json_err: # Handle cases where AI output isn't valid JSON
            log_error(f"OpenAI response was not valid JSON: {json_err}. Raw response snippet: {ai_result_str[:500]}")
        except openai.APIError as api_err: # Handle specific OpenAI API errors (network, rate limits, auth etc.)
            log_error(f"OpenAI API Error occurred: {api_err}.")
        except Exception as e: # Handle any other unexpected errors during the API call or processing
            log_error(f"Unexpected error during OpenAI API call or processing: {str(e)}.")

        # If any exception occurs in the try block, log warning and fall through to rule-based.
        log_warning("OpenAI call failed or an error occurred in processing its response. Falling back to rule-based mapping.")

    # --- Rule-Based Fallback Implementation ---
    # This section is reached if:
    # - 'rule_based' was the selected_provider.
    # - An AI provider was selected, but its library was unavailable, API key was missing, or client initialization failed.
    # - The OpenAI API call attempt failed (due to API error, JSON parsing error, or other exception).
    # Determine if we need to run rule-based:
    # - If selected_provider was 'rule_based' initially.
    # - If selected_provider was an AI but attempt_ai_call_for_provider was not set (e.g., lib missing, key missing, client init failed).
    # - If attempt_ai_call_for_provider was set (e.g. "openai") but the try-except block above was entered due to API call failure.

    # The log_func needs to be defined if it wasn't in the AI path or if an error occurred early.
    # This is a bit redundant with the top definition but ensures it's available if flow is complex.
    if 'log_info' not in locals(): # Check one of them
        try: from flask import current_app; app_logger_fb = current_app.logger
        except RuntimeError: app_logger_fb = None
        log_info = app_logger_fb.info if app_logger_fb else print
        log_warning = app_logger_fb.warning if app_logger_fb else print
        log_error = app_logger_fb.error if app_logger_fb else print
        log_debug = app_logger_fb.debug if app_logger_fb else print

    log_info("Executing rule-based mapping.")

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
    if num_unmapped > 0 and app_logger:
        app_logger.debug(f"Unmapped fields details (rule-based): {unmapped_fields_details}")
    elif num_unmapped > 0:
         print(f"Unmapped fields details (rule-based): {unmapped_fields_details}")

    return inferred_mappings, None


if __name__ == '__main__':
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
