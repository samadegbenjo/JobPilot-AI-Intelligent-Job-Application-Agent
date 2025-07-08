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

    // API Key elements
    const aiServiceKeyElement = document.getElementById('aiServiceKey');

    // Action elements
    const saveSettingsButton = document.getElementById('saveSettings');
    const statusMessageElement = document.getElementById('statusMessage');

    let resumeFileContent = null; // To store the base64 content of the resume file

    /**
     * Loads settings from chrome.storage.local and populates the popup form.
     * Fetches autoFillEnabled, userProfile, apiKeys, and resumeFileName.
     */
    function loadSettings() {
        chrome.storage.local.get([
            'autoFillEnabled',
            'userProfile',
            'apiKeys',
            'resumeFileName',
            // 'resumeFileContent' // Content is loaded on file selection, not stored directly unless small
        ], (result) => {
            if (result.autoFillEnabled !== undefined) {
                autoFillToggle.checked = result.autoFillEnabled;
            }

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

            if (result.apiKeys) {
                aiServiceKeyElement.value = result.apiKeys.aiServiceKey || '';
            }

            if (result.resumeFileName) {
                resumeFileNameElement.textContent = `Current: ${result.resumeFileName}`;
            }
        });
    }

    /**
     * Saves the current settings from the popup form to chrome.storage.local.
     * Stores autoFillEnabled, userProfile, apiKeys, and resumeFileContent/Name.
     * Displays a status message upon completion or error.
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

        const apiKeys = {
            // IMPORTANT: Storing API keys directly in chrome.storage.local is convenient for development
            // but is NOT SECURE for production. An attacker with access to the browser's profile
            // could potentially extract these keys.
            // For production, a backend proxy that securely stores and uses the API keys is recommended.
            // The extension would then authenticate with your proxy.
            aiServiceKey: aiServiceKeyElement.value.trim(),
        };

        const settingsToSave = {
            autoFillEnabled: autoFillToggle.checked,
            userProfile: userProfile,
            apiKeys: apiKeys,
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
    // Currently, its state is saved only when the main "Save Settings" button is clicked.
    // Consider immediate saving or messaging background script if behavior needs to be instant.
    autoFillToggle.addEventListener('change', () => {
        // Example of immediate action (currently commented out):
        // chrome.storage.local.set({ autoFillEnabled: autoFillToggle.checked });
        // chrome.runtime.sendMessage({ type: 'AUTOFILL_TOGGLED', enabled: autoFillToggle.checked });
        // showStatusMessage(`Auto-fill ${autoFillToggle.checked ? 'enabled' : 'disabled'}. Save settings to persist.`, false);
    });

    // Initial call to load settings when the popup is opened.
    loadSettings();
});
