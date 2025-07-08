console.log("Job Application Assistant: Background script (Service Worker) started.");

// --- Event Listeners ---
try {
    /**
     * @summary Listener for extension installation or update.
     * @description Initializes default settings in `chrome.storage.local` if they don't already exist.
     * This includes setting `autoFillEnabled` to false, and ensuring `userProfile`, `apiKeys`,
     * and `parsedResumeData` have initial empty/null states.
     * @param {chrome.runtime.InstalledDetails} details - Object containing details about the installation/update.
     */
    chrome.runtime.onInstalled.addListener((details) => {
        console.log("Extension installed or updated:", details.reason);
        // Initialize default settings if needed
        chrome.storage.local.get(['autoFillEnabled', 'userProfile', 'apiKeys', 'parsedResumeData'], (result) => {
            if (result.autoFillEnabled === undefined) {
                chrome.storage.local.set({ autoFillEnabled: false });
                console.log("Default 'autoFillEnabled' set to false.");
            }
            if (!result.userProfile) {
                chrome.storage.local.set({ userProfile: {} });
                console.log("Default 'userProfile' initialized.");
            }
            if (!result.apiKeys) {
                chrome.storage.local.set({ apiKeys: {} });
                console.log("Default 'apiKeys' initialized.");
            }
            if (!result.parsedResumeData) {
                chrome.storage.local.set({ parsedResumeData: null });
                console.log("Default 'parsedResumeData' initialized to null.");
            }
        });
    });

    /**
     * @summary Main message listener for communications from popup or content scripts.
     * @description Handles various message types:
     *  - `SETTINGS_UPDATED`: When settings (including resume) are saved from the popup.
     *    If a new resume is present, it triggers backend parsing.
     *  - `INITIATE_PAGE_FILL`: (New) Triggered by the "Fill Current Page" button in the popup.
     *    Calls `orchestratePageFill` to manage the full AI-driven filling process.
     *  - `TRIGGER_FILL_FORM`: (Legacy) Previously used for simpler fill actions. Now also routes
     *    to `orchestratePageFill` for a consistent filling experience.
     *  - `GET_STORED_DATA_FOR_FILLING`: (Potentially from content script) to request data needed for filling.
     * @param {Object} message - The message object, should have a `type` or `action` property.
     * @param {chrome.runtime.MessageSender} sender - Information about the message sender.
     * @param {Function} sendResponse - Callback to send a response.
     * @returns {boolean} True to indicate an asynchronous response, especially for `SETTINGS_UPDATED` with resume parsing
     *                    and `GET_STORED_DATA_FOR_FILLING`.
     */
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        console.log("Background received message:", message.type || message.action, "from sender:", sender.tab ? `tab ${sender.tab.id}`: "popup/extension", message);

        if (message.type === "SETTINGS_UPDATED") {
            console.log("Processing SETTINGS_UPDATED from popup.");
            // If resume content is part of the settings, parse it via the backend.
            if (message.settings.resumeFileContent && message.settings.resumeFileName) {
                parseResumeWithBackend(message.settings.resumeFileContent, message.settings.resumeFileName)
                    .then(parsedData => {
                        chrome.storage.local.set({ parsedResumeData: parsedData, lastResumeParseStatus: 'success' });
                        console.log("Resume parsed and stored successfully:", parsedData);
                        sendResponse({ status: "success", message: "Settings received, resume parsing successful." });
                    })
                    .catch(error => {
                        console.error("Background: Error parsing resume:", error);
                        chrome.storage.local.set({ parsedResumeData: null, lastResumeParseStatus: 'error', lastResumeParseError: error.message });
                        sendResponse({ status: "error", message: `Resume parsing failed: ${error.message}` });
                    });
                return true; // Indicates asynchronous response due to parseResumeWithBackend.
            } else if (message.settings.resumeFileContent === null && message.settings.resumeFileName === null) {
                // This case handles when the resume is explicitly cleared in the popup.
                chrome.storage.local.set({ parsedResumeData: null, lastResumeParseStatus: 'cleared' });
                console.log("Stored resume data has been cleared as per settings update.");
            }
            // If no resume parsing, respond.
            sendResponse({ status: "success", message: "Settings received by background (no new resume or resume cleared)." });
            return false;

        } else if (message.action === "TRIGGER_FILL_FORM") { // This is the older trigger, now less used.
            console.log("Processing legacy TRIGGER_FILL_FORM. Re-routing to orchestratePageFill.");
            orchestratePageFill();
            sendResponse({ status: "success", message: "Legacy fill form process initiated via orchestration." });
            return false;

        } else if (message.action === "INITIATE_PAGE_FILL") { // New trigger from popup button
            console.log("Processing INITIATE_PAGE_FILL.");
            orchestratePageFill();
            // orchestratePageFill is async and handles its own user feedback potentially.
            // Responding immediately to popup to acknowledge.
            sendResponse({ status: "success", message: "Page fill process initiated by background." });
            return false; // Let orchestratePageFill run.

        } else if (message.action === "GET_STORED_DATA_FOR_FILLING") {
            console.log("Processing GET_STORED_DATA_FOR_FILLING.");
            chrome.storage.local.get(['userProfile', 'parsedResumeData', 'autoFillEnabled', 'employmentQuestions'], (data) => {
                if (chrome.runtime.lastError) {
                    console.error("Error getting stored data for filling:", chrome.runtime.lastError);
                    sendResponse({ status: "error", message: "Failed to retrieve data."});
                    return;
                }
                if (data.autoFillEnabled) {
                    sendResponse({ status: "success", ...data });
                } else {
                    sendResponse({ status: "disabled", message: "Auto-fill is disabled." });
                }
            });
            return true; // Indicates asynchronous response due to chrome.storage.local.get.
        }

        // If the message type/action is not handled above, it's good practice to indicate it.
        // However, returning true keeps the message channel open, which might be desired if other listeners exist.
        // console.log("Message not explicitly handled by primary if/else:", message.type || message.action);
        return true; // Keep channel open for other potential listeners or future async operations.
    });

    /**
     * @summary Listener for extension commands (e.g., keyboard shortcuts defined in manifest.json).
     * @description Handles the "trigger_autofill" command to initiate form filling.
     * @param {string} command - The name of the command that was triggered.
     */
    chrome.commands.onCommand.addListener((command) => {
        if (command === "trigger_autofill") {
            console.log("Autofill command triggered by keyboard shortcut!");
            triggerFillActiveTab();
        }
    });

} catch (e) {
    // Catching potential errors during listener setup.
    console.error("Error setting up listeners in background script:", e);
}


// --- Core Functions ---

/**
 * @summary Legacy trigger for form filling, now redirects to `orchestratePageFill`.
 * @description This function was previously the main entry point for filling forms (e.g., via context menu
 * or keyboard shortcuts). It now calls `orchestratePageFill` to ensure all fill actions
 * use the same comprehensive, AI-driven logic.
 */
async function triggerFillActiveTab() {
    // This function is now a simple wrapper around orchestratePageFill.
    // It's kept for compatibility with context menu and keyboard shortcuts.
    console.log("Legacy triggerFillActiveTab called, now redirecting to orchestratePageFill.");
    orchestratePageFill();
}

/**
 * @summary Orchestrates the entire multi-step process of intelligently filling a form on the active page.
 * @description This is the core function for the "Fill Current Page" feature. It performs the following:
 *              1.  Retrieves the currently active browser tab.
 *              2.  Loads all necessary user data from `chrome.storage.local`. This includes:
 *                  - User profile details (name, contact, links).
 *                  - Parsed resume data.
 *                  - Auto-fill enabled status.
 *                  - Answers to employment-related questions.
 *                  - The selected AI provider (e.g., 'openai', 'gemini', 'rule_based').
 *                  - Stored API keys for the AI providers.
 *              3.  Checks if auto-fill is enabled and if essential user data is present. Aborts if not.
 *              4.  Consolidates all user data into a `comprehensiveUserData` object.
 *              5.  Determines the selected AI provider and retrieves the corresponding API key.
 *              6.  Communicates with the content script (`js/content.js`) on the active tab to:
 *                  a.  Extract all identifiable form fields from the webpage (`EXTRACT_FORM_FIELDS` action).
 *              7.  If fields are successfully extracted:
 *                  a.  Calls `getAIFieldMappings`, passing the extracted fields, `comprehensiveUserData` (for context),
 *                      the `selectedProvider`, and its `apiKey`. This function communicates with the Python backend.
 *                  b.  The backend (using `ai_handler.py`) will attempt to use the specified AI provider
 *                      (or rule-based logic) to map the webpage fields to standard user data keys.
 *              8.  If `getAIFieldMappings` returns a valid mapping:
 *                  a.  Sends the `FILL_FORM_WITH_AI_MAP` action to the content script, along with
 *                      `comprehensiveUserData` and the AI-generated `aiFieldMap`. The content script then populates the form.
 *              9.  Includes fallback mechanisms:
 *                  - If field extraction fails or no fields are found, it may attempt a `FILL_FORM_NAIVE`.
 *                  - If AI mapping fails or returns an empty map, it falls back to `FILL_FORM_NAIVE`.
 *              10. Handles errors, such as the content script not being injected (attempts to inject and retry),
 *                  or other communication issues.
 */
async function orchestratePageFill() {
    console.log("Orchestrating page fill process...");
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab || !tab.id) {
        console.warn("No active tab found or tab ID is missing for page fill orchestration.");
        // Future: could send a message back to popup if it needs to display an error.
        return;
    }

    chrome.storage.local.get([
        'userProfile',
        'parsedResumeData',
        'autoFillEnabled',
        'employmentQuestions',
        'selectedAiProvider', // NEW: To get the chosen AI provider
        'apiKeys'             // NEW: To get all stored API keys
    ], async (storageData) => {
        if (chrome.runtime.lastError) {
            console.error("Error retrieving data from storage for page fill:", chrome.runtime.lastError);
            return;
        }

        if (!storageData.autoFillEnabled) {
            console.log("Auto-fill is disabled by user. Aborting fill orchestration.");
            // Future: could send a message back to popup.
            return;
        }

        // Consolidate all user data. Parsed resume data is base, profile overrides, employment questions add to it.
        const comprehensiveUserData = {
            ...(storageData.parsedResumeData || {}),    // Base: data extracted from resume
            ...(storageData.userProfile || {}),         // Override/add: data from user profile fields
            ...(storageData.employmentQuestions || {})  // Add: data from employment questions
        };

        // Ensure customNotes is correctly sourced if it exists in userProfile
        if (storageData.userProfile && storageData.userProfile.customNotes) {
            comprehensiveUserData.customNotes = storageData.userProfile.customNotes;
        } else if (storageData.parsedResumeData && storageData.parsedResumeData.customNotes) { // Fallback if not in profile
            comprehensiveUserData.customNotes = storageData.parsedResumeData.customNotes;
        } else {
            comprehensiveUserData.customNotes = ''; // Default to empty if not found anywhere
        }


        if (Object.keys(comprehensiveUserData).length === 0 && !comprehensiveUserData.customNotes) { // Check if truly empty
             console.log("No user data (profile, resume, employment questions) available. Aborting page fill.");
             return;
        }
        console.log("Comprehensive user data prepared for filling/AI context:", comprehensiveUserData);

        const selectedProvider = storageData.selectedAiProvider || 'rule_based'; // Default to rule_based
        let apiKey = null;
        if (storageData.apiKeys && selectedProvider !== 'rule_based') {
            apiKey = storageData.apiKeys[selectedProvider.toLowerCase()]; // e.g., apiKeys['openai']
        }

        if (selectedProvider !== 'rule_based' && !apiKey) {
            console.warn(`AI provider '${selectedProvider}' selected, but its API key is missing or empty. ` +
                         `Filling may be attempted with rule-based logic or fail if AI is strictly required by backend.`);
            // Consider informing the user via the popup status message.
        }

        try {
            // Step 1: Ask content script to extract form fields from the page.
            console.log(`Sending EXTRACT_FORM_FIELDS to tab ${tab.id}`);
            const extractionResponse = await chrome.tabs.sendMessage(tab.id, { action: "EXTRACT_FORM_FIELDS" });

            if (!(extractionResponse && extractionResponse.status === "success" && extractionResponse.fields && extractionResponse.fields.length > 0)) {
                console.warn("Could not extract fields or no fields found on page. Attempting naive fill as fallback.");
                // Fallback to naive filling if field extraction fails or returns no fields.
                await chrome.tabs.sendMessage(tab.id, { action: "FILL_FORM_NAIVE", formData: comprehensiveUserData });
                return; // End orchestration here for this case.
            }

            console.log("Successfully extracted", extractionResponse.fields.length, "fields from content script.");

            // Step 2: Get field mappings from AI (or rule-based via backend).
            // Pass all user data for context, plus the selected AI provider and its key.
            const mappedFields = await getAIFieldMappings(
                extractionResponse.fields,
                comprehensiveUserData, // For context if AI needs it
                selectedProvider,
                apiKey
            );

            if (mappedFields && Object.keys(mappedFields).length > 0) {
                console.log("Received field map (from AI/Rules):", mappedFields);
                // Step 3: Tell content script to fill the form using the derived map.
                await chrome.tabs.sendMessage(tab.id, {
                    action: "FILL_FORM_WITH_AI_MAP",
                    userData: comprehensiveUserData,
                    aiFieldMap: mappedFields
                });
                console.log("Sent FILL_FORM_WITH_AI_MAP to content script.");
            } else {
                console.warn("AI/Rule-based mapping returned empty or failed. Falling back to naive fill.");
                await chrome.tabs.sendMessage(tab.id, { action: "FILL_FORM_NAIVE", formData: comprehensiveUserData });
            }

        } catch (error) {
            console.error("Error during page fill orchestration:", error);
            // Handle common error: content script not injected.
            if (error.message && error.message.includes("Receiving end does not exist")) {
                console.log("Content script might not be injected. Attempting to inject...");
                try {
                    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['js/content.js'] });
                    console.log("Content script injected. Retrying with naive fill as a simpler first attempt post-injection.");
                    // Retry with naive fill as it's simpler than full AI orchestration again immediately.
                    await chrome.tabs.sendMessage(tab.id, { action: "FILL_FORM_NAIVE", formData: comprehensiveUserData });
                } catch (injectionError) {
                    console.error("Failed to inject content script or send message after injection:", injectionError);
                }
            } else {
                // For other errors, attempt a naive fill as a last resort.
                console.error("An unexpected error occurred during the fill process:", error);
                try {
                    console.warn("Attempting naive fill due to previous errors in orchestration.");
                    await chrome.tabs.sendMessage(tab.id, { action: "FILL_FORM_NAIVE", formData: comprehensiveUserData });
                } catch (naiveFillError) {
                    console.error("Naive fill also failed after orchestration error:", naiveFillError);
                }
            }
        }
    });
}

// --- Backend Communication ---
// (parseResumeWithBackend remains the same for now, its JSDoc is assumed to be up-to-date from previous steps)

/**
 * @summary Sends resume content to the Python backend for parsing.
 * @description Extracts the base64 data from the data URL, then POSTs it along with the
 * file name to the `/parse_resume` endpoint of the Python backend.
 * @param {string} fileContentBase64 - The base64 encoded data URL of the resume file (e.g., "data:application/pdf;base64,JVBERi...").
 * @param {string} fileName - The original name of the file (e.g., "my_resume.pdf").
 * @returns {Promise<Object>} A promise that resolves with the parsed resume data object from the backend.
 * @throws {Error} If the backend returns an error or communication fails.
 */
async function parseResumeWithBackend(fileContentBase64, fileName) {
    console.log(`Background: Sending '${fileName}' to backend for parsing.`);
    const backendUrl = 'http://127.0.0.1:5000/parse_resume';
    const base64Data = fileContentBase64.split(',')[1]; // Extract actual base64 string

    try {
        const response = await fetch(backendUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_content_base64: base64Data,
                file_name: fileName,
            }),
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `HTTP error ${response.status}` }));
            throw new Error(`Backend error (parse_resume): ${errorData.detail || response.statusText}`);
        }
        const data = await response.json();
        if (data.error) { throw new Error(data.error); }
        console.log("Background: Parsed resume data received from backend:", data.parsed_data);
        return data.parsed_data;
    } catch (error) {
        console.error("Background: Error in parseResumeWithBackend communication:", error);
        throw error; // Re-throw to be handled by the caller
    }
}

/**
 * @summary Sends extracted form fields, user data context, selected AI provider, and API key to the Python backend.
 * @description The backend's `/infer_fields` endpoint will use this information (ideally with an AI model specified
 * by `selectedAiProvider`) to generate a mapping between webpage form fields and standard user data keys.
 *
 * @param {Array<Object>} fields - An array of field descriptor objects extracted by `content.js`.
 *                                 Each object contains details like `id`, `name`, `labelText`, `type`, etc.
 * @param {Object} userData - The comprehensive user data object (profile, resume, employment Qs)
 *                            to provide context to the AI for more accurate mapping.
 * @param {string} selectedAiProvider - A string identifying the AI provider selected by the user
 *                                      (e.g., 'openai', 'gemini', 'claude', 'rule_based').
 * @param {string|null} apiKey - The API key for the `selectedAiProvider`. Null if 'rule_based' or key not set.
 * @returns {Promise<Object|null>} A promise that resolves with an object mapping standardized keys
 *                                 to page field identifiers (e.g., `{ "firstName": "input_id_123" }`),
 *                                 or `null` if an error occurs or no mapping is generated.
 * @throws {Error} If the backend communication fails or the backend returns a critical error.
 */
async function getAIFieldMappings(fields, userData, selectedAiProvider, apiKey) {
    console.log(`Requesting AI field mappings. Provider: ${selectedAiProvider}. API Key Provided: ${!!apiKey}. Fields count: ${fields.length}.`);
    const backendUrl = 'http://127.0.0.1:5000/infer_fields';
    // Note: Security comment about API key handling from previous step still applies.

    try {
        const response = await fetch(backendUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                fields: fields,
                user_data_context: userData, // Send full user data for context
                selected_ai_provider: selectedAiProvider,
                api_key: apiKey
            }),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(`Backend error for AI mapping: ${errorData.detail || response.status}`);
        }
        const data = await response.json();
        console.log("AI field mapping suggestions from backend:", data);
        if(data.error) {
            throw new Error(data.error);
        }
        return data.mapped_fields; // Assuming this is the structure
    } catch (error) {
        console.error("Error getting AI field mappings from backend:", error);
        throw error;
    }
}

// Example of how the background script might proactively trigger on navigation,
// if autoFillEnabled is true and the URL matches a job site (more advanced).
/*
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url) {
        chrome.storage.local.get(['autoFillEnabled', 'jobSitePatterns'], (data) => {
            if (data.autoFillEnabled && data.jobSitePatterns) {
                const isJobSite = data.jobSitePatterns.some(pattern => new RegExp(pattern).test(tab.url));
                if (isJobSite) {
                    console.log(`Job site detected: ${tab.url}. Checking for forms.`);
                    // Could try to extract fields and then decide to fill
                    // Or directly try to fill if confidence is high
                    // chrome.tabs.sendMessage(tabId, { action: "EXTRACT_FORM_FIELDS" }, (response) => {
                    //    if (response && response.fields && response.fields.length > 0) {
                    //        console.log("Forms detected, could proceed with filling.");
                    //        triggerFillActiveTab(); // Or a more nuanced fill
                    //    }
                    // });
                }
            }
        });
    }
});
*/

// Add a context menu item to trigger autofill
chrome.contextMenus.create({
  id: "autofillJobForm",
  title: "Auto-fill Job Form",
  contexts: ["page", "frame"]
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "autofillJobForm" && tab) {
    triggerFillActiveTab();
  }
});
