document.addEventListener('DOMContentLoaded', () => {
    // Configuration elements
    const autoFillToggle = document.getElementById('autoFillToggle');

    // Resume elements
    const resumeFileElement = document.getElementById('resumeFile');
    const resumeFileNameElement = document.getElementById('resumeFileName');

    // Profile elements
    const fullNameElement = document.getElementById('fullName');
    const emailElement = document.getElementById('email');
    const phoneElement = document.getElementById('phone');
    const addressElement = document.getElementById('address');
    const linkedinElement = document.getElementById('linkedin');
    const githubElement = document.getElementById('github');
    const portfolioElement = document.getElementById('portfolio');
    const customNotesElement = document.getElementById('customNotes');

    // --- AI Configuration UI Elements ---
    /** @type {HTMLSelectElement} Dropdown for selecting AI provider. */
    const aiProviderSelect = document.getElementById('aiProvider');
    /** @type {HTMLInputElement} Input for OpenAI API key. */
    const openaiApiKeyInput = document.getElementById('openaiApiKey');
    /** @type {HTMLInputElement} Input for Gemini API key. */
    const geminiApiKeyInput = document.getElementById('geminiApiKey');
    /** @type {HTMLInputElement} Input for Claude API key. */
    const claudeApiKeyInput = document.getElementById('claudeApiKey');
    /** @type {HTMLDivElement} Div container for OpenAI API key input. */
    const apiKeyOpenAIGroup = document.getElementById('apiKeyOpenAI');
    /** @type {HTMLDivElement} Div container for Gemini API key input. */
    const apiKeyGeminiGroup = document.getElementById('apiKeyGemini');
    /** @type {HTMLDivElement} Div container for Claude API key input. */
    const apiKeyClaudeGroup = document.getElementById('apiKeyClaude');

    // --- Employment Questions UI Elements ---
    /** @type {HTMLSelectElement} Dropdown for visa status. */
    const visaStatusElement = document.getElementById('visaStatus');
    /** @type {HTMLSelectElement} Dropdown for work authorization. */
    const workAuthorizationElement = document.getElementById('workAuthorization');
    /** @type {HTMLSelectElement} Dropdown for relocation preference. */
    const relocationElement = document.getElementById('relocation');
    /** @type {HTMLInputElement} Text input for relocation specifics. */
    const relocationSpecificsElement = document.getElementById('relocationSpecifics');
    /** @type {HTMLInputElement} Text input for desired salary. */
    const desiredSalaryElement = document.getElementById('desiredSalary');
    /** @type {HTMLInputElement} Date input for availability date. */
    const availabilityDateElement = document.getElementById('availabilityDate');

    // --- Action UI Elements ---
    /** @type {HTMLButtonElement} Button to trigger filling the current page. */
    const fillCurrentPageButton = document.getElementById('fillCurrentPageButton');
    /** @type {HTMLButtonElement} Button to save all settings. */
    const saveSettingsButton = document.getElementById('saveSettings');
    /** @type {HTMLParagraphElement} Element to display status messages. */
    const statusMessageElement = document.getElementById('statusMessage');

    /** @type {string|ArrayBuffer|null} Stores the base64 content of the resume file. */
    let resumeFileContent = null;

    /**
     * Loads settings from chrome.storage.local and populates the popup form.
     * Fetches `autoFillEnabled`, `userProfile`, `selectedAiProvider`, `apiKeys` (object per provider),
     * `resumeFileName`, and `employmentQuestions`.
     */
    function loadSettings() {
        chrome.storage.local.get([
            'autoFillEnabled',          // Boolean: Whether auto-fill is globally enabled
            'userProfile',              // Object: User's personal and contact information
            'selectedAiProvider',       // String: Identifier for the chosen AI provider (e.g., 'openai', 'gemini')
            'apiKeys',                  // Object: Stores API keys, keyed by provider name (e.g., apiKeys.openai)
            'resumeFileName',           // String: Name of the last uploaded resume file
            'employmentQuestions'       // Object: User's answers to common employment-related questions
        ], (result) => {
            if (result.autoFillEnabled !== undefined) {
                autoFillToggle.checked = result.autoFillEnabled;
            }

            // Load User Profile
            if (result.userProfile) {
                fullNameElement.value = result.userProfile.fullName || '';
                emailElement.value = result.userProfile.email || '';
                phoneElement.value = result.userProfile.phone || '';
                addressElement.value = result.userProfile.address || '';
                linkedinElement.value = result.userProfile.linkedin || '';
                githubElement.value = result.userProfile.github || '';
                portfolioElement.value = result.userProfile.portfolio || '';
                customNotesElement.value = result.userProfile.customNotes || '';
            }

            // Load Employment Questions
            if (result.employmentQuestions) {
                visaStatusElement.value = result.employmentQuestions.visaStatus || '';
                workAuthorizationElement.value = result.employmentQuestions.workAuthorization || '';
                relocationElement.value = result.employmentQuestions.relocation || '';
                relocationSpecificsElement.value = result.employmentQuestions.relocationSpecifics || '';
                desiredSalaryElement.value = result.employmentQuestions.desiredSalary || '';
                availabilityDateElement.value = result.employmentQuestions.availabilityDate || '';
                toggleRelocationSpecifics(); // Ensure correct visibility
            }

            // Load AI Provider and API Keys
            if (result.selectedAiProvider) {
                aiProviderSelect.value = result.selectedAiProvider;
            }
            toggleApiKeyVisibility(); // Show the correct API key input based on selection

            if (result.apiKeys) {
                openaiApiKeyInput.value = result.apiKeys.openai || '';
                geminiApiKeyInput.value = result.apiKeys.gemini || '';
                claudeApiKeyInput.value = result.apiKeys.claude || '';
            }

            if (result.resumeFileName) {
                resumeFileNameElement.textContent = `Current: ${result.resumeFileName}`;
            }
        });
    }

    /**
     * Saves all current settings from the popup form to `chrome.storage.local`.
     * This includes:
     * - `autoFillEnabled` (boolean)
     * - `userProfile` (object with name, contact details, etc.)
     * - `selectedAiProvider` (string: 'openai', 'gemini', etc.)
     * - `apiKeys` (object: { openai: "key1", gemini: "key2", ... })
     * - `employmentQuestions` (object with visa status, relocation preference, etc.)
     * - `resumeFileContent` (string: base64 data URL of the resume, if a new one is staged)
     * - `resumeFileName` (string: name of the resume file)
     * Displays a status message upon successful save or if an error occurs.
     * Also sends a 'SETTINGS_UPDATED' message to the background script.
     */
    function saveSettings() {
        const userProfile = {
            fullName: fullNameElement.value.trim(),
            email: emailElement.value.trim(),
            phone: phoneElement.value.trim(),
            address: addressElement.value.trim(),
            linkedin: linkedinElement.value.trim(),
            github: githubElement.value.trim(),
            portfolio: portfolioElement.value.trim(),
            customNotes: customNotesElement.value.trim(),
        };

        const employmentQuestions = {
            visaStatus: visaStatusElement.value,
            workAuthorization: workAuthorizationElement.value,
            relocation: relocationElement.value,
            relocationSpecifics: relocationSpecificsElement.value.trim(),
            desiredSalary: desiredSalaryElement.value.trim(),
            availabilityDate: availabilityDateElement.value,
        };

        const apiKeys = {
            openai: openaiApiKeyInput.value.trim(),
            gemini: geminiApiKeyInput.value.trim(),
            claude: claudeApiKeyInput.value.trim(),
            // Add other provider keys here if new ones are added
        };

        const settingsToSave = {
            autoFillEnabled: autoFillToggle.checked,
            userProfile: userProfile,
            selectedAiProvider: aiProviderSelect.value,
            apiKeys: apiKeys,
            employmentQuestions: employmentQuestions,
        };

        // If a new resume file has been selected and processed, include its content and name
        if (resumeFileContent && resumeFileElement.files[0]) {
            settingsToSave.resumeFileContent = resumeFileContent; // Store as base64 or ArrayBuffer
            settingsToSave.resumeFileName = resumeFileElement.files[0].name;
        } else if (!resumeFileElement.files[0] && !resumeFileNameElement.textContent.includes('Current:')) {
            // If no file is selected and no old file name is there, clear stored resume
            settingsToSave.resumeFileContent = null;
            settingsToSave.resumeFileName = null;
        }


        chrome.storage.local.set(settingsToSave, () => {
            if (chrome.runtime.lastError) {
                showStatusMessage(`Error saving settings: ${chrome.runtime.lastError.message}`, true);
            } else {
                showStatusMessage('Settings saved successfully!', false);
                if (settingsToSave.resumeFileName) {
                     resumeFileNameElement.textContent = `Current: ${settingsToSave.resumeFileName}`;
                } else if (!resumeFileElement.files[0]) {
                    resumeFileNameElement.textContent = ''; // Clear if no file
                }
                // Send a message to the background script if autoFillEnabled changed
                chrome.runtime.sendMessage({ type: 'SETTINGS_UPDATED', settings: settingsToSave });
            }
        });
    }

    /**
     * Handles the resume file input ('change' event).
     * Reads the selected file, validates its size (max 5MB), and stores its content as a base64 data URL.
     * Updates the UI to display the selected file name or an error message.
     * The actual file content (`resumeFileContent`) is stored in a variable and only saved
     * to `chrome.storage.local` when the user clicks "Save Settings".
     * @param {Event} event - The file input change event, containing the selected file.
     */
    resumeFileElement.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            if (file.size > 5 * 1024 * 1024) { // 5MB limit for practical client-side handling
                showStatusMessage('File is too large (max 5MB).', true);
                resumeFileElement.value = ''; // Clear the input
                resumeFileNameElement.textContent = 'No resume selected or previous one retained.';
                resumeFileContent = null;
                return;
            }

            const reader = new FileReader();
            reader.onload = (e) => {
                resumeFileContent = e.target.result; // This will be ArrayBuffer or base64 string
                resumeFileNameElement.textContent = `Selected: ${file.name}`;
                showStatusMessage(`Resume "${file.name}" selected. Click "Save Settings".`, false);
            };
            reader.onerror = () => {
                showStatusMessage(`Error reading file: ${reader.error}`, true);
                resumeFileContent = null;
                resumeFileNameElement.textContent = 'Error reading file.';
            };
            // Read as ArrayBuffer, can be easily sent to backend or converted to base64 if needed
            reader.readAsDataURL(file); // Read as base64 data URL
                                        // For ArrayBuffer: reader.readAsArrayBuffer(file);
        } else {
            resumeFileNameElement.textContent = 'No resume selected.';
            resumeFileContent = null;
        }
    });

    /**
     * Displays a status message to the user in the popup.
     * The message automatically disappears after 3 seconds.
     * @param {string} message - The message to display.
     * @param {boolean} [isError=false] - If true, styles the message as an error.
     */
    function showStatusMessage(message, isError = false) {
        statusMessageElement.textContent = message;
        statusMessageElement.className = 'status-message'; // Reset classes
        if (isError) {
            statusMessageElement.classList.add('error');
        } else {
            statusMessageElement.classList.add('success');
        }
        setTimeout(() => {
            statusMessageElement.textContent = '';
            statusMessageElement.className = 'status-message';
        }, 3000); // Hide message after 3 seconds
    }

    // --- Event Listeners & Initialization ---

    // Attaches the saveSettings function to the "Save Settings" button click.
    saveSettingsButton.addEventListener('click', saveSettings);

    // Listener for the auto-fill toggle switch.
    autoFillToggle.addEventListener('change', () => {
        // Current behavior: state saved via "Save All Settings" button.
        // For immediate effect, could call saveSettings() or send a specific message.
    });

    /**
     * Shows or hides the API key input fields based on the currently selected AI Provider.
     * For "rule_based", all API key fields are hidden.
     * For specific AI providers (e.g., "openai", "gemini"), the corresponding API key field is shown.
     */
    function toggleApiKeyVisibility() {
        const selectedProvider = aiProviderSelect.value;
        // Hide all first, then show the relevant one.
        apiKeyOpenAIGroup.style.display = 'none';
        apiKeyGeminiGroup.style.display = 'none';
        apiKeyClaudeGroup.style.display = 'none';

        if (selectedProvider === 'openai') {
            apiKeyOpenAIGroup.style.display = 'block';
        } else if (selectedProvider === 'gemini') {
            apiKeyGeminiGroup.style.display = 'block';
        } else if (selectedProvider === 'claude') {
            apiKeyClaudeGroup.style.display = 'block';
        }
        // Add more providers here with else if blocks if needed.
    }

    /**
     * Shows or hides the 'relocationSpecifics' text input field based on the
     * selection in the 'relocation' dropdown. It's shown only if "Yes (Specific locations only)"
     * is selected.
     */
    function toggleRelocationSpecifics() {
        relocationSpecificsElement.style.display = (relocationElement.value === 'yes_specific') ? 'block' : 'none';
    }

    // --- Event Listeners for UI Interactivity & Actions ---

    // Attaches toggleApiKeyVisibility to the AI provider dropdown change event.
    aiProviderSelect.addEventListener('change', toggleApiKeyVisibility);

    // Attaches toggleRelocationSpecifics to the relocation dropdown change event.
    relocationElement.addEventListener('change', toggleRelocationSpecifics);

    /**
     * Event listener for the "Fill Current Page" button.
     * Sends a message to the background script (`background.js`) to initiate the
     * full page filling orchestration process. Handles basic response feedback.
     */
    fillCurrentPageButton.addEventListener('click', () => {
        showStatusMessage('Initiating page fill...', false);
        chrome.runtime.sendMessage({ action: 'INITIATE_PAGE_FILL' }, (response) => {
            if (chrome.runtime.lastError) {
                const errorMsg = `Error sending fill request: ${chrome.runtime.lastError.message}`;
                console.error(errorMsg);
                showStatusMessage(errorMsg, true);
            } else if (response && response.status === 'error') {
                const errorMsg = `Fill request failed: ${response.message}`;
                console.error(errorMsg);
                showStatusMessage(errorMsg, true);
            } else if (response && response.status === 'success') {
                showStatusMessage(response.message || 'Page fill process started successfully.', false);
            } else {
                // This case might occur if background script doesn't send a response or an unexpected one.
                console.warn("Unexpected or no response from background for INITIATE_PAGE_FILL action.", response);
                showStatusMessage('Fill process initiated. Check page or console for details.', false);
            }
        });
    });

    // --- Initialization ---
    // Initial call to load settings when the popup is opened.
    // This will also trigger toggleApiKeyVisibility and toggleRelocationSpecifics via the setters in loadSettings.
    loadSettings();
});
