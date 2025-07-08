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
     *  - `TRIGGER_FILL_FORM`: Initiates the form filling process on the active tab using the naive fill method.
     *                         (Note: The more advanced AI-driven fill is not yet fully wired here in `triggerFillActiveTab`)
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
            return false; // Or true if other async operations could happen for SETTINGS_UPDATED without resume. For now, false.

        } else if (message.action === "TRIGGER_FILL_FORM") {
            console.log("Processing TRIGGER_FILL_FORM.");
            triggerFillActiveTab(); // This function is async itself.
            // sendResponse should ideally be called by triggerFillActiveTab or related async chain if response depends on it.
            // For now, acknowledge receipt.
            sendResponse({ status: "success", message: "Fill form process initiated." });
            return false; // triggerFillActiveTab handles its own errors/logging.

        } else if (message.action === "GET_STORED_DATA_FOR_FILLING") {
            console.log("Processing GET_STORED_DATA_FOR_FILLING.");
            chrome.storage.local.get(['userProfile', 'parsedResumeData', 'autoFillEnabled'], (data) => {
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
 * @summary Triggers the form filling process on the currently active tab.
 * @description This function retrieves user data (profile, parsed resume) and auto-fill settings from storage.
 * If auto-fill is enabled and data is available, it sends a message to the content script (`js/content.js`)
 * on the active tab, instructing it to fill the form using the "FILL_FORM" action (which currently implies
 * the naive filling logic in content.js). It also handles basic error scenarios like content script
 * not being injected, attempting to inject it and retry.
 * Note: This version of `triggerFillActiveTab` does not yet implement the advanced flow of
 * extracting fields, then calling AI for mapping, then filling. It uses a simpler direct fill command.
 */
async function triggerFillActiveTab() {
    console.log("Attempting to trigger form fill on active tab.");
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab || !tab.id) {
        console.warn("No active tab found or tab ID is missing. Cannot trigger fill.");
        return;
    }

    chrome.storage.local.get(['userProfile', 'parsedResumeData', 'autoFillEnabled', 'customNotes'], async (data) => {
        if (chrome.runtime.lastError) {
            console.error("Error retrieving data from storage for triggerFillActiveTab:", chrome.runtime.lastError);
                return;
            }

            if (!data.autoFillEnabled) {
                console.log("Auto-fill is disabled. Aborting fill.");
                // Optionally, notify the user via popup or a small notification
                return;
            }

            if (!data.userProfile && !data.parsedResumeData) {
                console.log("No profile or resume data found to fill the form.");
                // Notify user
                return;
            }

            // Combine profile and parsed resume data
            // Prioritize profile data in case of overlap, or define a clear merge strategy
            const formData = {
                ...(data.parsedResumeData || {}), // Parsed resume data might include name, email, phone
                ...(data.userProfile || {}),      // User profile explicitly set by user
                customNotes: data.userProfile?.customNotes || '' // Ensure customNotes is included
            };

            console.log("Data prepared for filling:", formData);

            try {
                const response = await chrome.tabs.sendMessage(tab.id, { action: "FILL_FORM", formData: formData });
                console.log("Response from content script:", response);
                if (response && response.status === "success") {
                    console.log("Form filling initiated successfully by content script.");
                } else {
                    console.warn("Content script reported an issue or did not respond as expected:", response);
                }
            } catch (error) {
                console.error("Error sending message to content script or an error occurred in the content script:", error);
                // This often means the content script isn't injected or isn't listening.
                // Or the tab is a protected page (e.g., chrome:// pages)
                // Attempt to inject the content script if it seems to be missing.
                if (error.message.includes("Receiving end does not exist")) {
                    console.log("Content script might not be injected. Attempting to inject...");
                    try {
                        await chrome.scripting.executeScript({
                            target: { tabId: tab.id },
                            files: ['js/content.js']
                        });
                        // Try sending the message again after injection
                        const retryResponse = await chrome.tabs.sendMessage(tab.id, { action: "FILL_FORM", formData: formData });
                        console.log("Response from content script after injection:", retryResponse);
                    } catch (injectionError) {
                        console.error("Failed to inject content script or send message after injection:", injectionError);
                    }
                }
            }
        });
    } else {
        console.log("No active tab found to fill form.");
    }
}


// --- Backend Communication (Placeholders) ---

/**
 * Sends resume content to the Python backend for parsing.
 * @param {string} fileContentBase64 - The base64 encoded content of the resume file.
 * @param {string} fileName - The original name of the file.
 * @returns {Promise<Object>} A promise that resolves with the parsed resume data.
 */
async function parseResumeWithBackend(fileContentBase64, fileName) {
    console.log(`Background: Sending ${fileName} to backend for parsing.`);
    const backendUrl = 'http://127.0.0.1:5000/parse_resume'; // Ensure this matches your Flask app

    // The fileContentBase64 is already a data URL like "data:application/pdf;base64,JVBERi0xLjQKJ..."
    // We need to extract the actual base64 part.
    const base64Data = fileContentBase64.split(',')[1];

    try {
        const response = await fetch(backendUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_content_base64: base64Data,
                file_name: fileName,
            }),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            console.error("Backend error response:", errorData);
            throw new Error(`Backend error: ${errorData.detail || response.status}`);
        }

        const data = await response.json();
        console.log("Background: Parsed resume data from backend:", data);
        if (data.error) {
            throw new Error(data.error);
        }
        return data.parsed_data;
    } catch (error) {
        console.error("Background: Error communicating with or processing response from backend:", error);
        throw error; // Re-throw to be caught by caller
    }
}

/**
 * Sends form field context to the Python backend for AI-powered mapping/inference.
 * @param {Array<Object>} fields - Array of field objects extracted by the content script.
 * @returns {Promise<Object>} A promise that resolves with AI-suggested field mappings.
 */
async function getAIFieldMappings(fields) {
    console.log("Sending fields to backend for AI mapping:", fields);
    const backendUrl = 'http://127.0.0.1:5000/infer_fields'; // Ensure this matches your Flask app
    const { apiKeys } = await chrome.storage.local.get('apiKeys');
    // IMPORTANT: The API key is retrieved from chrome.storage.local here.
    // If this key were for a paid third-party AI service, sending it directly from the client-side
    // (even to your own backend) means it's exposed in transit and on the client.
    // A more secure production setup involves your backend having its own API key for the AI service,
    // and the extension authenticates with your backend, which then makes the AI call.
    // For this project's scope, we pass it, assuming the backend might need it if it were a proxy itself.

    try {
        const response = await fetch(backendUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                fields: fields,
                api_key: apiKeys ? apiKeys.aiServiceKey : null // Send API key if available
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
