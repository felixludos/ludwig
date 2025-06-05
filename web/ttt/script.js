$(document).ready(function() {
    // --- Core Game State & Constants ---
    const PLAYER_X = 'X';
    const PLAYER_O = 'O';
    const EMPTY = '_'; // Using underscore for empty in internal state string
    let currentPlayer = PLAYER_X;
    let boardState = Array(9).fill(EMPTY); // Internal representation: ['_', '_', '_', 'X', 'O', '_', '_', '_', '_']
    let gameActive = true;
    let isEditorMode = false;
    let conversationLogs = { X: [], O: [] }; // Separate logs

    // --- UI Elements Cache ---
    const ui = {
        boardDiv: $('#ticTacToeBoard'),
        statusEl: $('#status'),
        currentBoardStateEl: $('#currentBoardState'),
        useFrontendStubCheckbox: $('#useFrontendStub'),
        backendUrlInput: $('#backendUrl'),
        resetButton: $('#resetButton'),
        // Conversation Log UI
        toggleXConversationButton: $('#toggleXConversationButton'),
        toggleOConversationButton: $('#toggleOConversationButton'),
        llmConversationLogContainerX: $('#llmConversationLogContainerX'),
        llmConversationLogContainerO: $('#llmConversationLogContainerO'),
        llmConversationLogXEl: $('#llmConversationLogX'),
        llmConversationLogOEl: $('#llmConversationLogO'),
        clearLogButtons: $('.clear-log-button'),
        // LLM Settings
        llmModelSelectionEl: $('#llmModelSelection'),
        promptMethodSelectionEl: $('#promptMethodSelection'),
        llmPlayerControlSelect: $('#llmPlayerControl'),
        // Editor specific
        toggleEditorButton: $('#toggleEditorButton'),
        editorControlsEl: $('#editorControls'),
        editorClearBoardButton: $('#editorClearBoard'),
        editorPieceXRadio: $('#editorPieceX'),
        editorPieceORadio: $('#editorPieceO'),
        editorPieceEmptyRadio: $('#editorPieceEmpty'),
        editorTurnXRadio: $('#editorTurnX'),
        editorTurnORadio: $('#editorTurnO'),
        editorBoardStateInput: $('#editorBoardStateInput'),
        editorSetBoardStateButton: $('#editorSetBoardStateButton'),
        boardStateValidationMessageEl: $('#boardStateValidationMessage'),
        llmPlayFromPositionButton: $('#llmPlayFromPosition'),
    };

    // --- Game Logic Helpers ---
    function getLLMControlMode() { return ui.llmPlayerControlSelect.val(); } // 'O', 'X', 'both', 'neither'

    function isLLMsTurn(player = null) { // player can be PLAYER_X or PLAYER_O
        if (!gameActive || isEditorMode) return false;
        const controlMode = getLLMControlMode();
        const activePlayer = player || currentPlayer;

        if (controlMode === 'neither') return false;
        if (controlMode === 'both') return true; // LLM plays for the current player
        return controlMode === activePlayer; // LLM plays if it's assigned to the current active player
    }

    const winningConditions = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8], // Rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8], // Columns
        [0, 4, 8], [2, 4, 6]  // Diagonals
    ];

    function checkWin() {
        for (let i = 0; i < winningConditions.length; i++) {
            const [a, b, c] = winningConditions[i];
            if (boardState[a] !== EMPTY && boardState[a] === boardState[b] && boardState[a] === boardState[c]) {
                return { winner: boardState[a], line: [a,b,c] };
            }
        }
        return null;
    }

    function checkDraw() {
        return !boardState.includes(EMPTY) && !checkWin();
    }

    function boardStateToString(stateArray = boardState) {
        return stateArray.join('');
    }

    function stringToBoardState(str) {
        if (typeof str === 'string' && str.length === 9) {
            return str.split('');
        }
        return Array(9).fill(EMPTY); // Default if invalid
    }

    // --- Display Update Functions ---
    function renderBoard() {
        ui.boardDiv.empty();
        boardState.forEach((cell, index) => {
            const cellDiv = $('<div></div>')
                .addClass('ttt-cell')
                .attr('data-index', index)
                .text(cell === EMPTY ? '' : cell);
            if (cell === PLAYER_X) cellDiv.addClass('X');
            if (cell === PLAYER_O) cellDiv.addClass('O');
            ui.boardDiv.append(cellDiv);
        });
        ui.currentBoardStateEl.val(boardStateToString());
    }

    function updateStatus() {
        if (!gameActive) {
            const winInfo = checkWin();
            if (winInfo) {
                ui.statusEl.text(`${winInfo.winner} Wins!`);
                winInfo.line.forEach(index => {
                    ui.boardDiv.find(`.ttt-cell[data-index=${index}]`).addClass('winning-cell');
                });
            } else if (checkDraw()) {
                ui.statusEl.text("It's a Draw!");
            }
            return;
        }
        ui.statusEl.text(`${currentPlayer} to move.`);
    }

    function updateDisplayElements() {
        renderBoard(); // Render board first as checkWin might add classes
        updateStatus();
    }

    function displayConversationLog(player) { // player is 'X' or 'O'
        const logEl = player === PLAYER_X ? ui.llmConversationLogXEl : ui.llmConversationLogOEl;
        const logData = conversationLogs[player];
        logEl.empty();
        if (!logData || logData.length === 0) {
            logEl.append($('<p>').text('No conversation to display.'));
            return;
        }
        logData.forEach(msg => { /* ... (Same as chess version's displayConversationLog, just targets correct logEl) ... */
            const senderClass = (msg.sender ? msg.sender.toLowerCase().replace(/\s+/g, '-') : 'system').replace(/[^a-z0-9-]/gi, '');
            const messageDiv = $('<div>').addClass('log-message').addClass(senderClass);
            messageDiv.append($('<span>').addClass('sender').text(msg.sender || 'System'));
            if(msg.type) messageDiv.append($('<span>').addClass('type').text(`Type: ${msg.type}`));
            let content = msg.content;
            if (typeof content === 'object') content = JSON.stringify(content, null, 2);
            if (msg.type && (msg.type.includes('prompt') || msg.type.includes('response') || msg.type.includes('board_state') || msg.type.includes('raw_script_output'))) {
                 messageDiv.append($('<pre>').text(content));
            } else {
                 messageDiv.append($('<div>').html(String(content).replace(/\n/g, '<br>')));
            }
            logEl.append(messageDiv);
        });
        logEl.scrollTop(logEl[0].scrollHeight);
    }

    // --- LLM Settings and Interaction ---
    async function fetchLLMSettingsOptions() {
        const baseUrl = ui.backendUrlInput.val();
        if (!baseUrl) { /* ... (Error handling as before) ... */ return; }
        try {
            const response = await fetch(`${baseUrl}/get-llm-settings-options`); // Endpoint needs to exist on backend
            if (!response.ok) throw new Error(`Failed to fetch TTT LLM settings: ${response.status} ${response.statusText}`);
            const options = await response.json();
            // Populate Models & Prompts (same logic as chess, just different options expected from backend)
            ['llmModelSelectionEl', 'promptMethodSelectionEl'].forEach(elKey => { /* ... (Same as chess version) ... */
                const targetEl = ui[elKey];
                const optionType = elKey === 'llmModelSelectionEl' ? 'models' : 'prompting_methods';
                const radioName = elKey === 'llmModelSelectionEl' ? 'ttt_model' : 'ttt_prompting_method'; // Note: changed radioName
                const title = elKey === 'llmModelSelectionEl' ? 'Select Model (Stubbed):' : 'Select Prompting Method (Stubbed):';
                targetEl.empty().append($('<h3>').text(title));
                if (options[optionType] && options[optionType].length > 0) {
                    const group = $('<div>').addClass('option-group');
                    options[optionType].forEach((opt, index) => {
                        const radioId = `${radioName}_opt_${opt.id.replace(/[^a-zA-Z0-9_]/g, "")}`;
                        group.append($('<input type="radio" required>').attr('name', radioName).attr('id', radioId).val(opt.id).prop('checked', index === 0));
                        group.append($('<label>').attr('for', radioId).addClass('radio-label').text(opt.name));
                        group.append($('<br>'));
                    });
                    targetEl.append(group);
                } else { targetEl.append($('<p>No options available.</p>'));}
            });
        } catch (error) { /* ... (Error handling as before) ... */
             console.error("Error fetching TTT LLM settings options:", error);
            ui.llmModelSelectionEl.html('<h3>Select Model (Stubbed):</h3><p>Error loading models.</p>');
            ui.promptMethodSelectionEl.html('<h3>Select Prompting Method (Stubbed):</h3><p>Error loading prompt methods.</p>');
        }
    }
    ui.backendUrlInput.on('change', fetchLLMSettingsOptions);

    async function makeLLMMove() {
        const llmPlayerForTurn = currentPlayer; // X or O
        if (!gameActive || isEditorMode || !isLLMsTurn(llmPlayerForTurn)) return;

        ui.statusEl.text(`LLM (${llmPlayerForTurn}) is thinking...`);
        let turnSpecificLog = [];

        const selectedModel = $('input[name="ttt_model"]:checked').val(); // Ensure radio name matches
        const selectedPrompt = $('input[name="ttt_prompting_method"]:checked').val(); // Ensure radio name matches
        let llmMoveIndex = -1;

        if (ui.useFrontendStubCheckbox.is(':checked')) {
            turnSpecificLog.push({sender: "System", type: "info", content: `Frontend LLM Stub for ${llmPlayerForTurn}.`});
            turnSpecificLog.push({sender: `LLM Stub (${llmPlayerForTurn})`, type: "input_board_state", content: boardStateToString()});
            await new Promise(resolve => setTimeout(resolve, 500 + Math.random() * 400));

            const availableCells = boardState.map((val, idx) => val === EMPTY ? idx : -1).filter(idx => idx !== -1);
            if (availableCells.length === 0) { /* ... (Error handling as before, add to turnSpecificLog) ... */
                 turnSpecificLog.push({sender: `LLM Stub (${llmPlayerForTurn})`, type: "error-log", content: "No available moves."});
                 conversationLogs[llmPlayerForTurn].push(...turnSpecificLog);
                 if (ui[llmPlayerForTurn === PLAYER_X ? 'llmConversationLogContainerX' : 'llmConversationLogContainerO'].is(':visible')) displayConversationLog(llmPlayerForTurn);
                 updateDisplayElements(); return;
            }
            llmMoveIndex = availableCells[Math.floor(Math.random() * availableCells.length)];
            turnSpecificLog.push({sender: `LLM Stub (${llmPlayerForTurn})`, type: "decision", content: `Decided to play at index ${llmMoveIndex}.`});
        } else {
            const backendUrl = ui.backendUrlInput.val();
            if (!backendUrl) { /* ... (Error handling as before, add to turnSpecificLog) ... */ return; }
            turnSpecificLog.push({sender: "Frontend", type: "request_to_backend", content: `Requesting LLM move for ${llmPlayerForTurn}. Model: ${selectedModel}, Prompt: ${selectedPrompt}`});
            turnSpecificLog.push({sender: "Frontend", type: "request_board_state", content: boardStateToString()});
            try {
                const response = await fetch(`${backendUrl}/get-llm-move`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ board_state: boardStateToString(), player_to_move: llmPlayerForTurn, selected_model_id: selectedModel, selected_prompting_method_id: selectedPrompt })
                });
                const data = await response.json();
                if (data.conversationLog) turnSpecificLog = turnSpecificLog.concat(data.conversationLog);
                if (!response.ok) { /* ... (Error handling as before, add to turnSpecificLog) ... */
                    const errorMsg = data.error || `HTTP error! Status: ${response.status}`;
                    turnSpecificLog.push({sender: "Backend", type: "error-log", content: errorMsg});
                    throw new Error(errorMsg);
                }
                llmMoveIndex = data.move_index; // Expecting a number 0-8
                if (llmMoveIndex === undefined || llmMoveIndex < 0 || llmMoveIndex > 8) throw new Error("Backend returned invalid move index.");
                turnSpecificLog.push({sender: "Backend", type: "response_to_frontend", content: `Suggests move at index: ${llmMoveIndex}`});
            } catch (error) { /* ... (Error handling as before, add to turnSpecificLog) ... */
                console.error(`Error getting LLM move for ${llmPlayerForTurn} from backend:`, error);
                ui.statusEl.text(`Error for ${llmPlayerForTurn}: ${error.message}.`);
                if (!turnSpecificLog.find(m => m.type && m.type.includes('error'))) {
                     turnSpecificLog.push({sender: "Frontend", type: "error-log", content: `Network/Request Error for ${llmPlayerForTurn}: ${error.message}`});
                }
                conversationLogs[llmPlayerForTurn].push(...turnSpecificLog);
                if (ui[llmPlayerForTurn === PLAYER_X ? 'llmConversationLogContainerX' : 'llmConversationLogContainerO'].is(':visible')) displayConversationLog(llmPlayerForTurn);
                return;
            }
        }

        // Apply LLM's move
        if (llmMoveIndex !== -1 && boardState[llmMoveIndex] === EMPTY) {
            boardState[llmMoveIndex] = llmPlayerForTurn;
            const winInfo = checkWin();
            if (winInfo) gameActive = false;
            else if (checkDraw()) gameActive = false;
            else currentPlayer = (llmPlayerForTurn === PLAYER_X) ? PLAYER_O : PLAYER_X;
        } else {
            turnSpecificLog.push({sender: "System", type: "error-log", content: `LLM (${llmPlayerForTurn}) chose invalid or occupied cell: ${llmMoveIndex}. Game state unchanged.`});
            console.warn(`LLM (${llmPlayerForTurn}) chose invalid or occupied cell: ${llmMoveIndex}`);
        }

        conversationLogs[llmPlayerForTurn].push(...turnSpecificLog);
        updateDisplayElements();
        if (ui[llmPlayerForTurn === PLAYER_X ? 'llmConversationLogContainerX' : 'llmConversationLogContainerO'].is(':visible')) displayConversationLog(llmPlayerForTurn);

        if (gameActive) triggerLLMMoveIfNeeded(); // For LLM vs LLM
    }

    function triggerLLMMoveIfNeeded() {
        if (isLLMsTurn(currentPlayer)) { // Check for the now current player
            const delay = getLLMControlMode() === 'both' ? (700 + Math.random() * 300) : (300 + Math.random() * 200);
            window.setTimeout(makeLLMMove, delay);
        }
    }

    // --- Board Click Handler (Human Move) ---
    ui.boardDiv.on('click', '.ttt-cell', function() {
        if (!gameActive || isEditorMode || isLLMsTurn(currentPlayer)) return;

        const clickedIndex = $(this).data('index');
        if (boardState[clickedIndex] === EMPTY) {
            boardState[clickedIndex] = currentPlayer;
            const winInfo = checkWin();
            if (winInfo) gameActive = false;
            else if (checkDraw()) gameActive = false;
            else currentPlayer = (currentPlayer === PLAYER_X) ? PLAYER_O : PLAYER_X;

            updateDisplayElements();
            if (gameActive) triggerLLMMoveIfNeeded();
        }
    });

    // --- Editor Mode Logic ---
    function initializeBoardForEditor(initialBoardStr = "_________") {
        boardState = stringToBoardState(initialBoardStr.replace(/ /g, EMPTY)); // Allow spaces or underscores
        currentPlayer = ui.editorTurnXRadio.is(':checked') ? PLAYER_X : PLAYER_O;
        gameActive = true; // Editor assumes game can be played from this state
        renderBoard();
        updateStatus(); // Reflects editor's chosen turn
        ui.currentBoardStateEl.val(boardStateToString()); // Show board string
        ui.editorBoardStateInput.val(boardStateToString());
    }

    ui.toggleEditorButton.on('click', function() {
        isEditorMode = !isEditorMode;
        ui.boardStateValidationMessageEl.text('');
        if (isEditorMode) {
            $(this).text('Exit Editor & Resume Play').addClass('active-editor');
            ui.editorControlsEl.show();
            gameActive = false; // Disable game logic while editing
            initializeBoardForEditor(boardStateToString()); // Load current game board into editor
            ui.statusEl.text("Editor Mode: Click cells to place selected piece. Then Exit or Play.");
        } else {
            $(this).text('Enter Editor Mode').removeClass('active-editor');
            ui.editorControlsEl.hide();
            // Board state is already in boardState array from editor clicks or "Set State"
            currentPlayer = ui.editorTurnXRadio.is(':checked') ? PLAYER_X : PLAYER_O;
            gameActive = true; // Re-enable game logic

            // Validate board before exiting (e.g., not already won/drawn if trying to play)
            const winInfo = checkWin();
            if(winInfo) gameActive = false; else if (checkDraw()) gameActive = false;

            updateDisplayElements();
            if (gameActive) triggerLLMMoveIfNeeded();
        }
    });

    ui.boardDiv.on('click', '.ttt-cell', function() { // Also handles editor clicks now
        if (!isEditorMode) return; // Game clicks handled by separate handler
        const clickedIndex = $(this).data('index');
        let pieceToPlace = EMPTY;
        if (ui.editorPieceXRadio.is(':checked')) pieceToPlace = PLAYER_X;
        else if (ui.editorPieceORadio.is(':checked')) pieceToPlace = PLAYER_O;

        boardState[clickedIndex] = pieceToPlace;
        renderBoard(); // Re-render to show change
        ui.currentBoardStateEl.val(boardStateToString()); // Update display
        ui.editorBoardStateInput.val(boardStateToString()); // Sync editor input
    });

    ui.editorClearBoardButton.on('click', function() {
        if (!isEditorMode) return;
        initializeBoardForEditor("_________"); // Use 9 underscores for empty
        ui.boardStateValidationMessageEl.text('');
    });

    ui.editorSetBoardStateButton.on('click', function() {
        if (!isEditorMode) return;
        const inputState = ui.editorBoardStateInput.val().trim().toUpperCase();
        ui.boardStateValidationMessageEl.removeClass('success error').text('');
        if (inputState.length === 9 && /^[XO_]{9}$/.test(inputState)) { // Validate: 9 chars, X, O, or _
            initializeBoardForEditor(inputState);
            ui.boardStateValidationMessageEl.text('Board state set!').addClass('success');
        } else {
            ui.boardStateValidationMessageEl.text('Invalid state string. Must be 9 chars (X, O, or _).').addClass('error');
        }
    });

    ui.llmPlayFromPositionButton.on('click', function() {
        if (!isEditorMode) return;
        ui.boardStateValidationMessageEl.text('');
        // Board state is already in boardState, turn is set by radio buttons
        currentPlayer = ui.editorTurnXRadio.is(':checked') ? PLAYER_X : PLAYER_O;
        gameActive = true; // Ready to play

        // Exit editor mode
        isEditorMode = false;
        ui.editorControlsEl.hide();
        ui.toggleEditorButton.text('Enter Editor Mode').removeClass('active-editor');

        const winInfo = checkWin(); // Check if position is already terminal
        if(winInfo) gameActive = false; else if (checkDraw()) gameActive = false;

        updateDisplayElements();
        if (gameActive) triggerLLMMoveIfNeeded();
    });

    // --- Reset and Log Toggling/Clearing ---
    function resetGame() {
        if (isEditorMode) { isEditorMode = false; ui.toggleEditorButton.text('Enter Editor Mode').removeClass('active-editor'); ui.editorControlsEl.hide(); }
        ui.boardStateValidationMessageEl.text('');

        boardState = Array(9).fill(EMPTY);
        currentPlayer = PLAYER_X;
        gameActive = true;
        conversationLogs = { X: [], O: [] };

        updateDisplayElements();
        // Hide log containers
        ui.llmConversationLogContainerX.hide(); ui.toggleXConversationButton.text("View X's LLM Convo");
        ui.llmConversationLogContainerO.hide(); ui.toggleOConversationButton.text("View O's LLM Convo");

        triggerLLMMoveIfNeeded(); // If LLM plays X
    }
    ui.resetButton.on('click', resetGame);

    ui.toggleXConversationButton.on('click', function() {
        ui.llmConversationLogContainerX.toggle();
        $(this).text(ui.llmConversationLogContainerX.is(':visible') ? "Hide X's Convo" : "View X's LLM Convo");
        if (ui.llmConversationLogContainerX.is(':visible')) displayConversationLog(PLAYER_X);
    });
    ui.toggleOConversationButton.on('click', function() {
        ui.llmConversationLogContainerO.toggle();
        $(this).text(ui.llmConversationLogContainerO.is(':visible') ? "Hide O's Convo" : "View O's LLM Convo");
        if (ui.llmConversationLogContainerO.is(':visible')) displayConversationLog(PLAYER_O);
    });
    ui.clearLogButtons.on('click', function() {
        const playerToClear = $(this).data('player');
        if (conversationLogs[playerToClear]) {
            conversationLogs[playerToClear] = [];
            const logContainer = playerToClear === PLAYER_X ? ui.llmConversationLogContainerX : ui.llmConversationLogContainerO;
            if (logContainer.is(':visible')) displayConversationLog(playerToClear);
        }
    });

    // --- Standard Event Listeners ---
    ui.llmPlayerControlSelect.on('change', function() { if (!isEditorMode) { updateDisplayElements(); triggerLLMMoveIfNeeded(); } });

    // --- Initial Setup ---
    fetchLLMSettingsOptions();
    resetGame(); // Initial call to set up board and game state
});
