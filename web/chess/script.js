$(document).ready(function() {
    // Core game state
    let board = null; // chessboard.js instance
    let game = new Chess(); // chess.js instance
    let isEditorMode = false;
    let conversationLogs = { white: [], black: [] }; // Separate logs for white and black

    // --- PIECE IMAGE PATH ---
    const localPiecePath = 'img/chesspieces/wikipedia/{piece}.png';
    const cdnPiecePath = 'https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/img/chesspieces/wikipedia/{piece}.png';
    const pieceThemeUrl = localPiecePath; // Default to local, ensure images are there or switch to cdnPiecePath

    // --- UI Elements Cache ---
    const ui = {
        statusEl: $('#status'),
        currentFenEl: $('#currentFen'),
        useFrontendStubCheckbox: $('#useFrontendStub'),
        backendUrlInput: $('#backendUrl'),
        resetButton: $('#resetButton'),
        // Conversation Log UI (Updated)
        toggleWhiteConversationButton: $('#toggleWhiteConversationButton'),
        toggleBlackConversationButton: $('#toggleBlackConversationButton'),
        llmConversationLogContainerWhite: $('#llmConversationLogContainerWhite'),
        llmConversationLogContainerBlack: $('#llmConversationLogContainerBlack'),
        llmConversationLogWhiteEl: $('#llmConversationLogWhite'),
        llmConversationLogBlackEl: $('#llmConversationLogBlack'),
        clearLogButtons: $('.clear-log-button'), // Class for both clear buttons

        llmModelSelectionEl: $('#llmModelSelection'),
        promptMethodSelectionEl: $('#promptMethodSelection'),
        llmPlayerControlSelect: $('#llmPlayerControl'),
        // Editor specific
        toggleEditorButton: $('#toggleEditorButton'),
        editorControlsEl: $('#editorControls'),
        editorClearBoardButton: $('#editorClearBoard'),
        editorStartPositionButton: $('#editorStartPosition'),
        editorFlipBoardButton: $('#editorFlipBoard'),
        editorTurnWhiteRadio: $('#editorTurnWhite'),
        editorTurnBlackRadio: $('#editorTurnBlack'),
        editorFenInputElement: $('#editorFenInput'),
        editorSetFenButton: $('#editorSetFenButton'),
        fenValidationMessageEl: $('#fenValidationMessage'),
        llmPlayFromPositionButton: $('#llmPlayFromPosition'),
        boardDiv: $('#board')
    };

    // --- Game Logic Helpers ---
    function getLLMControlMode() {
        return ui.llmPlayerControlSelect.val();
    }

    function isLLMsTurn(forColor = null) { // forColor can be 'w' or 'b' to check specifically
        if (game.game_over() || isEditorMode) return false;
        const controlMode = getLLMControlMode();
        const currentTurn = game.turn();

        if (controlMode === 'neither') return false;
        if (controlMode === 'both') {
            return forColor ? currentTurn === forColor : true;
        }
        
        const targetColor = (controlMode === 'white') ? 'w' : 'b';
        if (forColor) {
            return currentTurn === forColor && targetColor === forColor;
        }
        return currentTurn === targetColor;
    }


    // --- Display Update Functions ---
    function updateStatus() {
        let statusText = '';
        const moveColor = game.turn() === 'w' ? 'White' : 'Black';
        if (game.game_over()) {
            if (game.in_checkmate()) statusText = `CHECKMATE! ${moveColor === 'White' ? 'Black' : 'White'} wins.`;
            else if (game.in_draw()) statusText = 'DRAWN (various reasons).';
            else if (game.in_stalemate()) statusText = 'STALEMATE.';
            else statusText = 'GAME OVER.';
        } else {
            statusText = `${moveColor} to move.`;
            if (game.in_check()) statusText += ` ${moveColor} is in check.`;
        }
        ui.statusEl.text(statusText);
    }

    function updateFenDisplay() {
        if (isEditorMode && board) {
            ui.currentFenEl.val(board.fen() + " (Editor: pieces only, set turn below)");
        } else {
            ui.currentFenEl.val(game.fen());
        }
    }
    
    function updateDisplayElements() {
        updateStatus();
        updateFenDisplay();
    }

    function displayConversationLog(color) { // color is 'white' or 'black'
        const logEl = color === 'white' ? ui.llmConversationLogWhiteEl : ui.llmConversationLogBlackEl;
        const logData = conversationLogs[color];

        logEl.empty();
        if (logData.length === 0) {
            logEl.append($('<p>').text('No conversation to display.'));
            return;
        }
        logData.forEach(msg => {
            const senderClass = (msg.sender ? msg.sender.toLowerCase().replace(/\s+/g, '-') : 'system').replace(/[^a-z0-9-]/gi, '');
            const messageDiv = $('<div>').addClass('log-message').addClass(senderClass);
            messageDiv.append($('<span>').addClass('sender').text(msg.sender || 'System'));
            if(msg.type) messageDiv.append($('<span>').addClass('type').text(`Type: ${msg.type}`));
            let content = msg.content;
            if (typeof content === 'object') content = JSON.stringify(content, null, 2);
            if (msg.type && (msg.type.includes('prompt') || msg.type.includes('response') || msg.type.includes('tool_call') || msg.type.includes('raw_script_output') || msg.type.includes('fen'))) {
                 messageDiv.append($('<pre>').text(content));
            } else {
                 messageDiv.append($('<div>').html(String(content).replace(/\n/g, '<br>')));
            }
            logEl.append(messageDiv);
        });
        logEl.scrollTop(logEl[0].scrollHeight);
    }

    // --- LLM Settings and Interaction ---
    async function fetchLLMSettingsOptions() { /* ... (Same as before, no changes needed for dual logs) ... */
        const baseUrl = ui.backendUrlInput.val();
        if (!baseUrl) {
            console.warn("Backend URL is empty. Cannot fetch LLM settings.");
            ui.llmModelSelectionEl.html('<h3>Select Model:</h3><p>Backend URL not set.</p>');
            ui.promptMethodSelectionEl.html('<h3>Select Prompting Method:</h3><p>Backend URL not set.</p>');
            return;
        }
        try {
            const response = await fetch(`${baseUrl}/get-llm-settings-options`);
            if (!response.ok) throw new Error(`Failed to fetch LLM settings: ${response.status} ${response.statusText}`);
            const options = await response.json();

            ['llmModelSelectionEl', 'promptMethodSelectionEl'].forEach(elKey => {
                const targetEl = ui[elKey];
                const optionType = elKey === 'llmModelSelectionEl' ? 'models' : 'prompting_methods';
                const radioName = elKey === 'llmModelSelectionEl' ? 'llm_model' : 'prompting_method';
                const title = elKey === 'llmModelSelectionEl' ? 'Select Model:' : 'Select Prompting Method:';
                
                targetEl.empty().append($('<h3>').text(title));
                if (options[optionType] && options[optionType].length > 0) {
                    const group = $('<div>').addClass('option-group');
                    options[optionType].forEach((opt, index) => { 
                        const radioId = `${radioName}_opt_${opt.id.replace(/[^a-zA-Z0-9_]/g, "")}`;
                        group.append(
                            $('<input type="radio" required>')
                                .attr('name', radioName)
                                .attr('id', radioId)
                                .val(opt.id)
                                .prop('checked', index === 0)
                        );
                        group.append($('<label>').attr('for', radioId).addClass('radio-label').text(opt.name));
                        group.append($('<br>'));
                    });
                    targetEl.append(group);
                } else { targetEl.append($('<p>No options available.</p>'));}
            });
        } catch (error) { 
            console.error("Error fetching LLM settings options:", error);
            ui.llmModelSelectionEl.html('<h3>Select Model:</h3><p>Error loading models.</p>');
            ui.promptMethodSelectionEl.html('<h3>Select Prompting Method:</h3><p>Error loading prompt methods.</p>');
        }
    }
    ui.backendUrlInput.on('change', fetchLLMSettingsOptions);

    async function makeLLMMove() {
        const llmColorForTurn = game.turn(); // 'w' or 'b'
        const logTargetColor = llmColorForTurn === 'w' ? 'white' : 'black';

        if (game.game_over() || isEditorMode || !isLLMsTurn(llmColorForTurn)) return;
        
        ui.statusEl.text(`LLM (${logTargetColor}) is thinking...`);
        // Do not clear logs here, they accumulate. Individual messages are pushed.

        const selectedModel = $('input[name="llm_model"]:checked').val();
        const selectedPrompt = $('input[name="prompting_method"]:checked').val();
        let llmMoveData = null;
        let turnSpecificLog = []; // Temporary log for this turn's messages

        if (ui.useFrontendStubCheckbox.is(':checked')) {
            turnSpecificLog.push({sender: "System", type: "info", content: `Frontend LLM Stub for ${logTargetColor}.`});
            turnSpecificLog.push({sender: `LLM Stub (${logTargetColor})`, type: "input_fen", content: game.fen()});
            await new Promise(resolve => setTimeout(resolve, 600 + Math.random() * 500));
            
            const possibleMoves = game.moves({ verbose: true });
            if (possibleMoves.length === 0) {
                turnSpecificLog.push({sender: `LLM Stub (${logTargetColor})`, type: "error-log", content: "No legal moves."});
                conversationLogs[logTargetColor].push(...turnSpecificLog);
                if (ui[logTargetColor === 'white' ? 'llmConversationLogContainerWhite' : 'llmConversationLogContainerBlack'].is(':visible')) displayConversationLog(logTargetColor);
                updateDisplayElements();
                return;
            }
            llmMoveData = possibleMoves[Math.floor(Math.random() * possibleMoves.length)];
            turnSpecificLog.push({sender: `LLM Stub (${logTargetColor})`, type: "decision", content: `Decided to play ${llmMoveData.san}.`});
            game.move(llmMoveData.san);
        } else {
            const backendUrl = ui.backendUrlInput.val();
            if (!backendUrl) { /* ... (error handling as before, add to turnSpecificLog) ... */ 
                turnSpecificLog.push({sender: "Frontend", type: "error-log", content: "Backend URL is not set."});
                ui.statusEl.text("Error: Backend URL not set.");
                conversationLogs[logTargetColor].push(...turnSpecificLog);
                if (ui[logTargetColor === 'white' ? 'llmConversationLogContainerWhite' : 'llmConversationLogContainerBlack'].is(':visible')) displayConversationLog(logTargetColor);
                return;
            }
            turnSpecificLog.push({sender: "Frontend", type: "request_to_backend", content: `Requesting LLM move for ${logTargetColor}. Model: ${selectedModel}, Prompt: ${selectedPrompt}`});
            turnSpecificLog.push({sender: "Frontend", type: "request_fen", content: game.fen()});
            try {
                const response = await fetch(`${backendUrl}/get-llm-move`, { 
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ fen: game.fen(), selected_model_id: selectedModel, selected_prompting_method_id: selectedPrompt })
                });
                const data = await response.json();
                if (data.conversationLog) turnSpecificLog = turnSpecificLog.concat(data.conversationLog); // Backend's log for this specific call
                if (!response.ok) { /* ... (error handling as before, add to turnSpecificLog) ... */
                    const errorMsg = data.error || `HTTP error! Status: ${response.status}`;
                    turnSpecificLog.push({sender: "Backend", type: "error-log", content: errorMsg});
                    throw new Error(errorMsg);
                }
                llmMoveData = data.move;
                if (!llmMoveData) throw new Error("Backend returned no move.");
                turnSpecificLog.push({sender: "Backend", type: "response_to_frontend", content: `Suggests move: ${llmMoveData}`});
                const moveResult = game.move(llmMoveData, { sloppy: true });
                if (!moveResult) { /* ... (error handling as before, add to turnSpecificLog) ... */
                    const invalidMoveError = `Invalid move from backend: '${llmMoveData}'. FEN: ${game.fen()}`;
                    turnSpecificLog.push({sender: "Frontend", type: "error-log", content: invalidMoveError});
                    throw new Error(invalidMoveError);
                }
            } catch (error) { 
                console.error(`Error getting LLM move for ${logTargetColor} from backend:`, error);
                ui.statusEl.text(`Error for ${logTargetColor}: ${error.message}.`);
                if (!turnSpecificLog.find(m => m.type && m.type.includes('error'))) {
                     turnSpecificLog.push({sender: "Frontend", type: "error-log", content: `Network/Request Error for ${logTargetColor}: ${error.message}`});
                }
                conversationLogs[logTargetColor].push(...turnSpecificLog);
                if (ui[logTargetColor === 'white' ? 'llmConversationLogContainerWhite' : 'llmConversationLogContainerBlack'].is(':visible')) displayConversationLog(logTargetColor);
                return; 
            }
        }
        
        conversationLogs[logTargetColor].push(...turnSpecificLog); // Add this turn's log to the persistent log
        board.position(game.fen());
        updateDisplayElements();
        if (ui[logTargetColor === 'white' ? 'llmConversationLogContainerWhite' : 'llmConversationLogContainerBlack'].is(':visible')) displayConversationLog(logTargetColor);
        triggerLLMMoveIfNeeded();
    }
    
    function triggerLLMMoveIfNeeded() {
        const nextTurnColor = game.turn();
        if (isLLMsTurn(nextTurnColor)) { // Check specifically for the color whose turn it is
            const delay = getLLMControlMode() === 'both' ? (800 + Math.random() * 400) : (200 + Math.random() * 200);
            window.setTimeout(makeLLMMove, delay);
        }
    }

    // --- Chessboard Event Handlers --- (Mostly same as before)
    function gameOnDragStart(source, piece) { /* ... Same as before ... */ 
        if (isEditorMode || game.game_over()) return false;
        const currentTurn = game.turn();
        if ((currentTurn === 'w' && piece.search(/^b/) !== -1) ||
            (currentTurn === 'b' && piece.search(/^w/) !== -1)) return false;

        const controlMode = getLLMControlMode();
        if (controlMode === 'both' || 
           (controlMode === 'white' && currentTurn === 'w') || 
           (controlMode === 'black' && currentTurn === 'b')) {
            return false; 
        }
        return true;
    }
    function gameOnDrop(source, target) { /* ... Same as before ... */ 
        if (isEditorMode) return; 
        const moveAttempt = { from: source, to: target, promotion: 'q' }; 
        const moveResult = game.move(moveAttempt);
        if (moveResult === null) return 'snapback';
        updateDisplayElements();
        triggerLLMMoveIfNeeded();
    }
    function gameOnSnapEnd() { /* ... Same as before ... */ 
        if (isEditorMode) return;
        board.position(game.fen());
    }
    function editorOnDragStart() { return true; } 
    function editorOnDrop(source, target, piece, newPos, oldPos, orientation) { updateFenDisplay(); }
    function editorOnSnapEnd() { updateFenDisplay(); }


    // --- Board Initialization --- (Mostly same as before)
    function initializeBoard(fenOrPosition = 'start') { /* ... Same as before ... */ 
        if (board) board.destroy();
        let boardConfig = { pieceTheme: pieceThemeUrl, position: fenOrPosition, draggable: true };
        if (isEditorMode) {
            boardConfig.dropOffBoard = 'trash'; boardConfig.sparePieces = true;
            boardConfig.onDrop = editorOnDrop; boardConfig.onDragStart = editorOnDragStart; boardConfig.onSnapEnd = editorOnSnapEnd;
            if (board && board.orientation() === 'black') boardConfig.orientation = 'black';
        } else {
            boardConfig.sparePieces = false; boardConfig.dropOffBoard = 'snapback';
            boardConfig.onDragStart = gameOnDragStart; boardConfig.onDrop = gameOnDrop; boardConfig.onSnapEnd = gameOnSnapEnd;
            boardConfig.orientation = 'white'; 
        }
        board = Chessboard('board', boardConfig);
        if (!isEditorMode) {
            const loadSuccess = game.load(fenOrPosition);
            if (!loadSuccess) { console.warn("Failed FEN load (game):", fenOrPosition); game.reset(); board.position(game.fen()); }
        } else {
            const currentBoardFen = board.fen(); const currentTurn = ui.editorTurnWhiteRadio.is(':checked') ? 'w' : 'b';
            game.load(`${currentBoardFen} ${currentTurn} - - 0 1`); ui.editorFenInputElement.val(currentBoardFen);
        }
        updateDisplayElements();
    }

    // --- Main Controls and Editor Button Handlers --- (Updated for dual logs)
    function resetGameToStart(fen = 'start') {
        if (isEditorMode) { isEditorMode = false; ui.toggleEditorButton.text('Enter Editor Mode').removeClass('active-editor'); ui.editorControlsEl.hide(); }
        ui.fenValidationMessageEl.text('');
        conversationLogs = { white: [], black: [] }; // Clear both logs
        
        initializeBoard(fen); 
        // Hide both log containers on reset, user can re-open
        ui.llmConversationLogContainerWhite.hide(); ui.toggleWhiteConversationButton.text("View White's LLM Convo");
        ui.llmConversationLogContainerBlack.hide(); ui.toggleBlackConversationButton.text("View Black's LLM Convo");
        // displayConversationLog('white'); displayConversationLog('black'); // No need, they are cleared and hidden

        triggerLLMMoveIfNeeded(); 
    }
    
    ui.toggleEditorButton.on('click', function() { /* ... (Same as before - handles editor UI, calls initializeBoard) ... */ 
        isEditorMode = !isEditorMode; ui.fenValidationMessageEl.text('');
        if (isEditorMode) {
            $(this).text('Exit Editor & Resume Play').addClass('active-editor'); ui.editorControlsEl.show();
            const currentPieceFen = game.fen().split(' ')[0]; initializeBoard(currentPieceFen); 
            if (game.turn() === 'w') ui.editorTurnWhiteRadio.prop('checked', true); else ui.editorTurnBlackRadio.prop('checked', true);
            ui.editorFenInputElement.val(board.fen()); ui.statusEl.text("Editor Mode: Setup board, then Exit or Play.");
        } else {
            $(this).text('Enter Editor Mode').removeClass('active-editor'); ui.editorControlsEl.hide();
            const editorFenPieces = board.fen(); const editorTurn = ui.editorTurnWhiteRadio.is(':checked') ? 'w' : 'b';
            const fullEditorFen = `${editorFenPieces} ${editorTurn} - - 0 1`; 
            initializeBoard(fullEditorFen); triggerLLMMoveIfNeeded(); 
        }
    });
    ui.editorClearBoardButton.on('click', function() { /* ... (Same as before - updates game, board, FEN input) ... */ 
        if (!isEditorMode || !board) return; board.clear(false); 
        const emptyFenPieces = '8/8/8/8/8/8/8/8'; ui.editorFenInputElement.val(emptyFenPieces);
        const currentTurn = ui.editorTurnWhiteRadio.is(':checked') ? 'w' : 'b';
        game.load(`${emptyFenPieces} ${currentTurn} - - 0 1`); updateDisplayElements(); ui.fenValidationMessageEl.text('');
    });
    ui.editorStartPositionButton.on('click', function() { /* ... (Same as before - updates game, board, FEN input) ... */ 
        if (!isEditorMode || !board) return; const startFen = new Chess().fen();
        board.position(startFen, false); game.load(startFen); 
        ui.editorFenInputElement.val(startFen.split(' ')[0]); 
        if (game.turn() === 'w') ui.editorTurnWhiteRadio.prop('checked', true); else ui.editorTurnBlackRadio.prop('checked', true);
        updateDisplayElements(); ui.fenValidationMessageEl.text('');
    });
    ui.editorFlipBoardButton.on('click', function() { if (board) board.flip(); });
    ui.editorSetFenButton.on('click', function() { /* ... (Same as before - validates FEN, updates game, board, turn radio) ... */
        if (!isEditorMode || !board) return; const inputFen = ui.editorFenInputElement.val().trim();
        ui.fenValidationMessageEl.text('').css('color', 'red'); const tempGame = new Chess();
        if (tempGame.load(inputFen)) { 
            game.load(inputFen); board.position(game.fen(), false); 
            if (game.turn() === 'w') ui.editorTurnWhiteRadio.prop('checked', true); else ui.editorTurnBlackRadio.prop('checked', true);
            updateDisplayElements(); ui.fenValidationMessageEl.text('FEN set successfully!').css('color', 'green');
        } else { const validation = tempGame.validate_fen(inputFen); ui.fenValidationMessageEl.text(`Invalid FEN: ${validation.error || 'Unknown reason'}`); }
    });
    ui.llmPlayFromPositionButton.on('click', function() { /* ... (Same as before - exits editor, loads FEN, calls initializeBoard & triggerLLM) ... */
        if (!isEditorMode || !board) return; ui.fenValidationMessageEl.text('');
        const editorFenPieces = board.fen(); const editorTurn = ui.editorTurnWhiteRadio.is(':checked') ? 'w' : 'b';
        const fullEditorFen = `${editorFenPieces} ${editorTurn} - - 0 1`; 
        isEditorMode = false; ui.editorControlsEl.hide(); ui.toggleEditorButton.text('Enter Editor Mode').removeClass('active-editor');
        initializeBoard(fullEditorFen); triggerLLMMoveIfNeeded(); 
    });
    
    // --- New Conversation Log Toggle/Clear Handlers ---
    ui.toggleWhiteConversationButton.on('click', function() {
        ui.llmConversationLogContainerWhite.toggle();
        $(this).text(ui.llmConversationLogContainerWhite.is(':visible') ? "Hide White's Convo" : "View White's LLM Convo");
        if (ui.llmConversationLogContainerWhite.is(':visible')) displayConversationLog('white');
    });
    ui.toggleBlackConversationButton.on('click', function() {
        ui.llmConversationLogContainerBlack.toggle();
        $(this).text(ui.llmConversationLogContainerBlack.is(':visible') ? "Hide Black's Convo" : "View Black's LLM Convo");
        if (ui.llmConversationLogContainerBlack.is(':visible')) displayConversationLog('black');
    });

    ui.clearLogButtons.on('click', function() {
        const colorToClear = $(this).data('color'); // 'white' or 'black'
        if (conversationLogs[colorToClear]) {
            conversationLogs[colorToClear] = [];
            // If the corresponding log view is visible, refresh it to show it's empty
            const logContainer = colorToClear === 'white' ? ui.llmConversationLogContainerWhite : ui.llmConversationLogContainerBlack;
            if (logContainer.is(':visible')) {
                displayConversationLog(colorToClear);
            }
        }
    });
    
    // --- Standard Event Listeners ---
    ui.llmPlayerControlSelect.on('change', function() { if (!isEditorMode) { updateDisplayElements(); triggerLLMMoveIfNeeded(); } });
    ui.resetButton.on('click', () => resetGameToStart()); 
    
    // --- Resize Observer for Board ---
    if (window.ResizeObserver && ui.boardDiv.length) {
        new ResizeObserver(() => { if(board) board.resize(); }).observe(ui.boardDiv[0]);
    } else { $(window).resize(() => { if(board) board.resize(); }); }
    
    // --- Initial Setup ---
    fetchLLMSettingsOptions(); 
    initializeBoard('start');  
    // triggerLLMMoveIfNeeded(); // initializeBoard calls updateDisplayElements, which can lead to this if LLM plays white
});
