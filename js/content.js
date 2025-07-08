console.log("Job Application Assistant: Content script loaded."); // Confirms script injection

let uniqueFieldCounter = 0; // Counter for generating unique temporary IDs for form fields without an ID.

/**
 * Listener for messages from the background script or popup.
 * Handles actions like filling forms (with AI map or naively) and extracting form fields.
 * @param {Object} message - The message object received.
 * @param {Object} sender - Information about the sender of the message.
 * @param {Function} sendResponse - Function to call to send a response back to the sender.
 * @returns {boolean} True to indicate that sendResponse will be called asynchronously.
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("Content.js received message:", message.action, message); // Log action and full message
    if (message.action === "FILL_FORM_WITH_AI_MAP") {
        // Preferred action: Fill form using AI-derived field mappings.
        if (message.userData && message.aiFieldMap) {
            fillFormFieldsWithAIMap(message.userData, message.aiFieldMap);
            sendResponse({ status: "success", message: "Form fields processed using AI map." });
        } else {
            sendResponse({ status: "error", message: "Missing userData or aiFieldMap for FILL_FORM_WITH_AI_MAP." });
        }
    } else if (message.action === "FILL_FORM_NAIVE") {
        // Fallback to naive filling if AI mapping isn't available or chosen
        if (message.formData) {
            fillFormFieldsNaive(message.formData);
            sendResponse({ status: "success", message: "Form fields processed with naive logic." });
        } else {
            sendResponse({ status: "error", message: "No formData provided for FILL_FORM_NAIVE." });
        }
    } else if (message.action === "EXTRACT_FORM_FIELDS") {
        const fields = extractFormFields();
        sendResponse({ status: "success", fields: fields });
    }
    return true; // Indicates that the response will be sent asynchronously
});

/**
 * Extracts identifiable form fields (inputs, textareas, selects) from the current webpage.
 * It gathers various attributes like id, name, type, placeholder, labels, and aria-attributes
 * to provide rich context for AI-based field mapping.
 * If a field lacks an 'id', a temporary one ('data-jaa-temp-id') is generated and assigned.
 *
 * @returns {Array<Object>} An array of objects, where each object represents a form field
 *                          and contains its extracted properties (e.g., tempId, id, name, type, labelText).
 */
function extractFormFields() {
    const selectors = 'input[type="text"], input[type="email"], input[type="tel"], input[type="url"], input[type="search"], input[type="number"], input[type="date"], textarea, select';
    const elements = document.querySelectorAll(selectors); // Gathers all relevant form elements
    const extractedFields = [];
    uniqueFieldCounter = 0; // Reset for each extraction

    elements.forEach(element => {
        let labelText = '';
        // Try to find a label associated with the input
        if (element.id) {
            const labelElement = document.querySelector(`label[for="${element.id}"]`);
            if (labelElement) {
                labelText = labelElement.textContent.trim();
            }
        }
        // If no direct label, try to find a parent label or aria-labelledby
        if (!labelText && element.closest('label')) {
            labelText = element.closest('label').textContent.trim();
        }
        if (!labelText && element.getAttribute('aria-labelledby')) {
            const labelledByElement = document.getElementById(element.getAttribute('aria-labelledby'));
            if (labelledByElement) {
                labelText = labelledByElement.textContent.trim();
            }
        }

        let tempId = element.id;
        if (!tempId) {
            tempId = `jaa-field-${uniqueFieldCounter++}`;
            element.setAttribute('data-jaa-temp-id', tempId); // Mark the element with a temporary ID if needed later
        }

        extractedFields.push({
            tempId: tempId, // Use this as the primary reference if original id is missing
            id: element.id || null,
            name: element.name || null,
            type: element.type ? element.type.toLowerCase() : element.tagName.toLowerCase(),
            placeholder: element.placeholder || null,
            ariaLabel: element.getAttribute('aria-label') || null,
            title: element.title || null,
            labelText: labelText || null, // Text from <label>
            value: element.value,
            tagName: element.tagName.toLowerCase(),
            // TODO: Could add surrounding text snippets for more context for AI
        });
    });
    console.log("Extracted fields for AI:", extractedFields);
    return extractedFields;
}

/**
 * Fills form fields on the webpage using a mapping provided by an AI service.
 * The `aiFieldMap` links standardized data keys (e.g., "firstName", "email")
 * to specific field identifiers (original ID or temporary 'data-jaa-temp-id') on the page.
 *
 * @param {Object} userData - An object containing all user data (e.g., from profile and parsed resume)
 *                            keyed by standardized names (e.g., userData.firstName).
 * @param {Object} aiFieldMap - An object mapping standard data keys to page field identifiers.
 *                              Example: { "firstName": "form_input_id_123", "email": "user_email_field_name" }
 */
function fillFormFieldsWithAIMap(userData, aiFieldMap) {
    console.log("Attempting to fill form with AI map. UserData:", userData, "AI Map:", aiFieldMap);

    for (const standardKey in aiFieldMap) {
        if (userData.hasOwnProperty(standardKey) && aiFieldMap.hasOwnProperty(standardKey)) {
            const pageFieldIdentifier = aiFieldMap[standardKey]; // This should be the tempId or original id
            const valueToFill = userData[standardKey];

            let elementToFill = document.getElementById(pageFieldIdentifier);
            if (!elementToFill) {
                elementToFill = document.querySelector(`[data-jaa-temp-id="${pageFieldIdentifier}"]`);
            }

            if (elementToFill && valueToFill !== undefined && valueToFill !== null) {
                console.log(`AI Map: Filling '${standardKey}' into field '${pageFieldIdentifier}' with value '${String(valueToFill).substring(0,50)}...'`);
                setValue(elementToFill, valueToFill);
            } else if (!elementToFill) {
                console.warn(`AI Map: Field with identifier '${pageFieldIdentifier}' for key '${standardKey}' not found on page.`);
            }
        }
    }

    // Handle customNotes separately if not explicitly mapped by AI, using heuristics
    if (userData.customNotes && !aiFieldMap.customNotes && !aiFieldMap.coverLetter) {
        fillCustomNotesHeuristically(userData.customNotes);
    }

    console.log("Form filling with AI map attempt complete.");
}


/**
 * Fills form fields using a predefined set of naive, keyword-based mappings.
 * This function serves as a fallback if AI mapping is unavailable or fails.
 * It iterates through all detectable form inputs and attempts to match them against
 * common keywords associated with standard user data fields (e.g., "fullName", "email").
 *
 * @param {Object} formData - An object containing user data, where keys are standardized
 *                            field names (e.g., "fullName") and values are the data to fill.
 */
function fillFormFieldsNaive(formData) {
    console.log("Attempting to fill form with NAIVE logic. Data:", formData);

    // `naiveFieldMappings` provides common keywords for each standard data field.
    const naiveFieldMappings = {
        // Profile Data
        'fullName': ['name', 'fullname', 'full name', 'your name', 'applicantname'],
        'firstName': ['firstname', 'first name', 'given name', 'fname', 'givenname'],
        'lastName': ['lastname', 'last name', 'surname', 'family name', 'lname', 'familyname'],
        'email': ['email', 'emailaddress', 'e-mail'],
        'phone': ['phone', 'phonenumber', 'telephone', 'mobile', 'contactnumber'],
        'address': ['address', 'street', 'streetaddress', 'addressline1', 'mailingaddress'],
        'linkedin': ['linkedin', 'linkedinurl', 'linkedin profile'],
        'github': ['github', 'githuburl', 'github profile'],
        'portfolio': ['portfolio', 'portfolio_url', 'website', 'personal website', 'homepage'],
    };

    const allInputs = document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"], input[type="url"], input[type="search"], textarea, select');

    allInputs.forEach(input => {
        let foundMatch = false;
        const inputId = input.id ? input.id.toLowerCase().replace(/[^a-z0-9]/gi, '') : ''; // Normalize
        const inputName = input.name ? input.name.toLowerCase().replace(/[^a-z0-9]/gi, '') : ''; // Normalize
        const inputPlaceholder = input.placeholder ? input.placeholder.toLowerCase() : '';
        let labelText = '';

        if (input.id) {
            const labelElement = document.querySelector(`label[for="${input.id}"]`);
            if (labelElement) {
                labelText = labelElement.textContent.trim().toLowerCase();
            }
        }

        for (const dataKey in formData) {
            if (formData.hasOwnProperty(dataKey) && naiveFieldMappings[dataKey]) {
                naiveFieldMappings[dataKey].forEach(keyword => {
                    if (foundMatch) return;
                    const normalizedKeyword = keyword.replace(/[^a-z0-9]/gi, '');

                    if (inputId === normalizedKeyword || inputName === normalizedKeyword ||
                        (input.getAttribute('aria-label') && input.getAttribute('aria-label').toLowerCase() === keyword)) {
                        setValue(input, formData[dataKey]);
                        foundMatch = true;
                    }
                    else if (labelText.includes(keyword) || inputId.includes(normalizedKeyword) || inputName.includes(normalizedKeyword) || inputPlaceholder.includes(keyword)) {
                        if (keyword.length < 5 && !(labelText.includes(dataKey) || inputName.includes(dataKey) || inputId.includes(dataKey))) {
                            // more cautious
                        } else {
                            setValue(input, formData[dataKey]);
                            foundMatch = true;
                        }
                    }
                });
            }
            if (foundMatch) break;
        }
    });

    // Fallback for custom notes / cover letter snippets
    if (formData.customNotes) {
       fillCustomNotesHeuristically(formData.customNotes);
    }
    console.log("Naive form filling attempt complete.");
}

/**
 * Heuristically identifies and fills large textareas that might be intended for
 * custom notes, cover letters, or additional information.
 * It avoids overwriting textareas already filled or those that seem to match
 * other specific field types based on keywords.
 *
 * @param {string} notes - The text content (e.g., user's custom notes or cover letter snippets) to fill into suitable textareas.
 */
function fillCustomNotesHeuristically(notes) {
    if (!notes) return; // Do nothing if no notes are provided.

    document.querySelectorAll('textarea').forEach(textarea => {
        // Skip if already filled by a more specific mapping or has significant content
        if (textarea.value && textarea.value.length > notes.length / 2) return;

        const textAriaKeywords = ['cover letter', 'additional information', 'summary', 'note', 'message', 'introduction', 'why you'];
        let labelText = '';
        if (textarea.id) {
            const labelElement = document.querySelector(`label[for="${textarea.id}"]`);
            if (labelElement) labelText = labelElement.textContent.trim().toLowerCase();
        }
        const placeholderText = textarea.placeholder ? textarea.placeholder.toLowerCase() : '';
        const nameText = textarea.name ? textarea.name.toLowerCase() : '';

        const mightBeCoverLetter = textAriaKeywords.some(kw =>
            labelText.includes(kw) || placeholderText.includes(kw) || nameText.includes(kw)
        );

        // Heuristic: large textareas, or those explicitly labeled for cover letter/notes
        if (mightBeCoverLetter || (textarea.rows >= 4 && !textarea.value)) {
            // Check if it was likely filled by a specific mapping already by checking against common profile fields
            // This is to avoid overwriting something like a "job duties" textarea if "customNotes" is generic
            let isLikelyOtherSpecificField = false;
            const specificKeywords = ['responsibilities', 'duties', 'experience', 'bio', 'skills'];
             if (specificKeywords.some(kw => labelText.includes(kw) || placeholderText.includes(kw) || nameText.includes(kw))) {
                isLikelyOtherSpecificField = true;
            }

            if (!isLikelyOtherSpecificField) {
                 console.log(`Heuristically filling textarea (${textarea.id || textarea.name || 'unidentified'}) with customNotes.`);
                 setValue(textarea, notes);
            }
        }
    });
}


/**
 * Sets the value of a given form element (input, select, textarea, checkbox, radio)
 * and dispatches 'input' and 'change' events to ensure that any JavaScript logic
 * on the webpage (e.g., from frameworks like React, Vue, Angular) reacts to the change as if a user typed it.
 *
 * @param {HTMLElement} element - The DOM element whose value is to be set.
 * @param {String|Boolean} value - The value to assign to the element. For checkboxes/radios,
 *                                 a boolean indicates checked state, or a string can match its 'value' attribute.
 */
function setValue(element, value) {
    if (!element || value === undefined || value === null) {
        // console.warn("setValue: Element is null or value is undefined/null for element:", element); // Useful for debugging
        return;
    }

    const tagName = element.tagName.toLowerCase();
    const type = element.type ? element.type.toLowerCase() : '';

    // console.log(`Setting value for ${element.id || element.name || element.type || element.tagName}: '${String(value).substring(0,50)}...'`);
    element.focus();

    if (tagName === 'select') {
        let optionFound = false;
        const valStr = String(value).toLowerCase();
        for (let i = 0; i < element.options.length; i++) {
            if (element.options[i].value.toLowerCase() === valStr || element.options[i].text.toLowerCase() === valStr) {
                element.selectedIndex = i;
                optionFound = true;
                break;
            }
        }
        if (!optionFound) { // Try partial match in text if no exact match
            for (let i = 0; i < element.options.length; i++) {
                if (element.options[i].text.toLowerCase().includes(valStr)) {
                    element.selectedIndex = i;
                    optionFound = true;
                    break;
                }
            }
        }
        if(!optionFound) console.warn(`setValue: Option '${value}' not found for select ${element.id || element.name}`);

    } else if (type === 'checkbox' || type === 'radio') {
        if (typeof value === 'boolean') {
            element.checked = value;
        } else { // If value is not boolean, try matching element.value
            element.checked = (element.value === String(value));
        }
    } else {
        element.value = String(value);
    }

    element.dispatchEvent(new Event('input', { bubbles: true, cancelable: true, composed: true }));
    element.dispatchEvent(new Event('change', { bubbles: true, cancelable: true, composed: true }));
    element.blur();
}

// Example: To test filling with an AI map, you would simulate a message:
// chrome.runtime.sendMessage({
//   action: "FILL_FORM_WITH_AI_MAP",
//   userData: { fullName: "AI Test User", email: "ai_test@example.com", customNotes: "These are AI notes." },
//   aiFieldMap: { fullName: "nameFieldId", email: "emailEntry", customNotes: "notesTextareaId" }
// });

// Example: To test naive filling:
// fillFormFieldsNaive({ fullName: "Test User", email: "test@example.com", customNotes: "Some notes for a large textarea." });
