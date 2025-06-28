$(document).ready(function() {
    // --- Global State & Configuration ---
    let currentGameId = null;
    let currentGame = null;
    let isEditorMode = false;
    let conversationLogs = { player1: [], player2: [] };

    // --- UI Elements Cache (Common) ---
    const ui = {
        gameSelector: $('#gameSelector'),
        dynamicBoardContainer: $('#dynamicBoardContainer'),
        statusEl: $('#status'),
        gameStateLabel: $('#gameStateLabel'),
        currentGameStateDisplay: $('#currentGameStateDisplay'),
        useFrontendStubCheckbox: $('#useFrontendStub'),
        backendUrlInput: $('#backendUrl'),
        resetButton: $('#resetButton'),
        togglePlayer1ConversationButton: $('#togglePlayer1ConversationButton'),
        togglePlayer2ConversationButton: $('#togglePlayer2ConversationButton'),
        llmConversationLogContainerPlayer1: $('#llmConversationLogContainerPlayer1'),
        llmConversationLogContainerPlayer2: $('#llmConversationLogContainerPlayer2'),
        llmConversationLogPlayer1El: $('#llmConversationLogPlayer1'),
        llmConversationLogPlayer2El: $('#llmConversationLogPlayer2'),
        player1LogTitle: $('#player1LogTitle'),
        player2LogTitle: $('#player2LogTitle'),
        clearLogButtons: $('.clear-log-button'),
        llmModelSelectionEl: $('#llmModelSelection'),
        promptMethodSelectionEl: $('#promptMethodSelection'),
        llmPlayerControlSelect: $('#llmPlayerControl'),
        toggleEditorButton: $('#toggleEditorButton'),
        editorControlsContainer: $('#editorControlsContainer'),
        editorClearBoardButton: $('#editorClearBoard'),
        gameSpecificEditorControls: $('#gameSpecificEditorControls'),
        editorTurnPlayer1Radio: $('#editorTurnPlayer1'),
        editorTurnPlayer2Radio: $('#editorTurnPlayer2'),
        editorTurnPlayer1Label: $('#editorTurnPlayer1Label'),
        editorTurnPlayer2Label: $('#editorTurnPlayer2Label'),
        llmPlayFromPositionButton: $('#llmPlayFromPosition'),
    };

    const loadedAssets = { css: {}, js: {} };
    function loadScript(url, callback) {
        if (loadedAssets.js[url]) { if (callback) callback(); return; }
        $.getScript(url, function() { loadedAssets.js[url] = true; if (callback) callback(); })
         .fail(function(jqxhr, settings, exception) { console.error("Failed to load script:", url, exception); });
    }
    function loadCSS(url) {
        if (loadedAssets.css[url]) return;
        $('<link>').appendTo('head').attr({type : 'text/css', rel : 'stylesheet'}).attr('href', url);
        loadedAssets.css[url] = true;
    }

    const gamesConfig = {
        tictactoe: {
            name: "Tic-Tac-Toe", player1Name: "X", player2Name: "O", assets: { js: [], css: [] },
            initGame: null, handleCellClick: null, getGameStateString: null, isLLMsTurnLogic: null,
            makeLLMMoveLogic: null, checkWinLogic: null, checkDrawLogic: null, resetGameLogic: null,
            setupEditorControls: null, getEditorBoardState: null, setBoardFromEditorState: null,
            clearEditorBoard: null, updateBoardUIVisuals: null,
            getLLMPlayerControlOptions: function() {
                return [
                    { value: this.player2Name, text: `${this.player2Name} (Player 2)` },
                    { value: this.player1Name, text: `${this.player1Name} (Player 1)` },
                    { value: 'both', text: `Both ${this.player1Name} & ${this.player2Name}` },
                    { value: 'neither', text: `Neither (Human vs Human)` }
                ];
            }
        },
        chess: {
            name: "Chess", player1Name: "White", player2Name: "Black",
            assets: {
                js: [ 'https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js',
                      'https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js' ],
                css: [ 'https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css' ]
            },
            initGame: null, getGameStateString: null, isLLMsTurnLogic: null, makeLLMMoveLogic: null,
            checkWinLogic: null, checkDrawLogic: null, resetGameLogic: null, setupEditorControls: null,
            getEditorBoardState: null, setBoardFromEditorState: null, clearEditorBoard: null,
            flipBoardEditor: null, startPositionEditor: null, updateBoardUIVisuals: null,
            handleResize: null,
            getLLMPlayerControlOptions: function() {
                 return [
                    { value: this.player2Name.toLowerCase(), text: `${this.player2Name}` },
                    { value: this.player1Name.toLowerCase(), text: `${this.player1Name}` },
                    { value: 'both', text: `Both ${this.player1Name} & ${this.player2Name}` },
                    { value: 'neither', text: `Neither (Human vs Human)` }
                ];
            }
        }
    };

    function loadGameAssets(gameId, callback) {
        const assets = gamesConfig[gameId].assets;
        let jsToLoad = assets.js.length;
        let cssToLoad = assets.css.length;
        if (jsToLoad === 0 && cssToLoad === 0) { if(callback) callback(); return; }
        assets.css.forEach(url => loadCSS(url));
        if (jsToLoad === 0) { if(callback) callback(); return; }
        assets.js.forEach(url => {
            loadScript(url, () => { jsToLoad--; if (jsToLoad === 0) { if (callback) callback(); } });
        });
    }

    function switchGame(newGameId) {
        if (currentGameId === newGameId && currentGame) return;
        currentGameId = newGameId; currentGame = gamesConfig[newGameId];
        ui.gameSelector.val(newGameId);
        ui.gameStateLabel.text(currentGameId === 'chess' ? "Current FEN:" : "Board State:");
        ui.llmPlayerControlSelect.empty();
        const playerOptions = currentGame.getLLMPlayerControlOptions();
        playerOptions.forEach(opt => ui.llmPlayerControlSelect.append($('<option>').val(opt.value).text(opt.text)));
        ui.llmPlayerControlSelect.val('neither');
        ui.player1LogTitle.text(`${currentGame.player1Name}'s LLM Convo`);
        ui.player2LogTitle.text(`${currentGame.player2Name}'s LLM Convo`);
        ui.togglePlayer1ConversationButton.text(`View ${currentGame.player1Name}'s Convo`);
        ui.togglePlayer2ConversationButton.text(`View ${currentGame.player2Name}'s Convo`);
        ui.clearLogButtons.each(function() {
            const player = $(this).data('player');
            $(this).text(`Clear ${player === 'player1' ? currentGame.player1Name : currentGame.player2Name}'s Log`);
        });
        ui.editorTurnPlayer1Label.text(currentGame.player1Name);
        ui.editorTurnPlayer2Label.text(currentGame.player2Name);

        loadGameAssets(newGameId, () => {
            console.log(`${currentGame.name} assets loaded. Initializing game.`);
            isEditorMode = false;
            ui.editorControlsContainer.hide();
            ui.toggleEditorButton.text('Enter Editor Mode').removeClass('active-editor');
            ui.gameSpecificEditorControls.empty();
            if (currentGame.setupEditorControls) currentGame.setupEditorControls();

            if (currentGame.initGame) {
                 // For chess, ensure it starts with the initial position by default
                if (newGameId === 'chess') {
                    currentGame.initGame(''); // Explicitly pass 'start'
                } else {
                    currentGame.initGame();
                }
            } else {
                console.error(`initGame function not defined for ${newGameId}`);
            }
            fetchLLMSettingsOptions();
        });
    }

    // --- Game-Agnostic UI & LLM Functions ---
    function updateStatus() { if (currentGame && currentGame.updateStatusLogic) currentGame.updateStatusLogic(); }
    function updateGameStateDisplay() { if (currentGame && currentGame.getGameStateString) ui.currentGameStateDisplay.val(currentGame.getGameStateString());}

    function updateDisplayElements() {
        if (currentGame && currentGame.updateBoardUIVisuals) {
            currentGame.updateBoardUIVisuals();
        }
        updateStatus();
        updateGameStateDisplay();
    }

    function displayConversationLog(playerIdentifier) {
        if (!currentGame) return;
        const playerLogData = conversationLogs[playerIdentifier];
        const logEl = playerIdentifier === 'player1' ? ui.llmConversationLogPlayer1El : ui.llmConversationLogPlayer2El;
        logEl.empty();
        if (!playerLogData || playerLogData.length === 0) { logEl.append($('<p>').text('No conversation to display.')); return; }
        playerLogData.forEach(msg => {
            const senderClass = (msg.sender ? msg.sender.toLowerCase().replace(/\s+/g, '-') : 'system').replace(/[^a-z0-9-]/gi, '');
            const messageDiv = $('<div>').addClass('log-message').addClass(senderClass);
            messageDiv.append($('<span>').addClass('sender').text(msg.sender || 'System'));
            if(msg.type) messageDiv.append($('<span>').addClass('type').text(`Type: ${msg.type}`));
            let content = msg.content;
            if (typeof content === 'object') content = JSON.stringify(content, null, 2);
            if (msg.type && (msg.type.includes('prompt') || msg.type.includes('response') || msg.type.includes('board_state') || msg.type.includes('fen') || msg.type.includes('raw_script_output'))) {
                 messageDiv.append($('<pre>').text(content));
            } else {
                 messageDiv.append($('<div>').html(String(content).replace(/\n/g, '<br>')));
            }
            logEl.append(messageDiv);
        });
        logEl.scrollTop(logEl[0].scrollHeight);
    }
    async function fetchLLMSettingsOptions() {
        const baseUrl = ui.backendUrlInput.val();
        if (!baseUrl) { ui.llmModelSelectionEl.html('<h3>Select Model:</h3><p>Backend URL not set.</p>'); ui.promptMethodSelectionEl.html('<h3>Select Prompting Method:</h3><p>Backend URL not set.</p>'); return; }
        try {
            const response = await fetch(`${baseUrl}/get-llm-settings-options?game=${currentGameId}`);
            if (!response.ok) throw new Error(`Failed to fetch LLM settings: ${response.status} ${response.statusText}`);
            const options = await response.json();
            ['llmModelSelectionEl', 'promptMethodSelectionEl'].forEach(elKey => {
                const targetEl = ui[elKey];
                const optionType = elKey === 'llmModelSelectionEl' ? 'models' : 'prompting_methods';
                const radioName = elKey === 'llmModelSelectionEl' ? `${currentGameId}_model` : `${currentGameId}_prompting_method`;
                const title = elKey === 'llmModelSelectionEl' ? 'Select Model:' : 'Select Prompting Method:';
                targetEl.empty().append($('<h3>').text(title));
                if (options[optionType] && options[optionType].length > 0) {
                    const group = $('<div>').addClass('option-group');
                    options[optionType].forEach((opt, index) => {
                        const radioId = `${radioName}_opt_${opt.id.replace(/[^a-zA-Z0-9_]/g, "")}`;
                        group.append($('<input type="radio" required>').attr('name', radioName).attr('id', radioId).val(opt.id).prop('checked', index === 0));
                        group.append($('<label>').attr('for', radioId).addClass('radio-label').text(opt.name)); group.append($('<br>'));
                    });
                    targetEl.append(group);
                } else { targetEl.append($('<p>No options available.</p>'));}
            });
        } catch (error) {
            console.error("Error fetching LLM settings:", error);
            ui.llmModelSelectionEl.html('<h3>Select Model:</h3><p>Error loading models.</p>');
            ui.promptMethodSelectionEl.html('<h3>Select Prompting Method:</h3><p>Error loading prompt methods.</p>');
        }
    }
    ui.backendUrlInput.on('change', fetchLLMSettingsOptions);

    async function makeLLMMove() {
        if (!currentGame || !currentGame.makeLLMMoveLogic || isEditorMode) return;
        await currentGame.makeLLMMoveLogic();
        triggerLLMMoveIfNeeded();
    }
    function triggerLLMMoveIfNeeded() {
        if (!currentGame || !currentGame.isLLMsTurnLogic || isEditorMode) return;
        if (currentGame.isLLMsTurnLogic()) {
            const delay = ui.llmPlayerControlSelect.val() === 'both' ? (700 + Math.random() * 300) : (300 + Math.random() * 200);
            window.setTimeout(makeLLMMove, delay);
        }
    }

    // --- Editor Mode (Common Logic) ---
    ui.toggleEditorButton.on('click', function() {
        isEditorMode = !isEditorMode;
        if (isEditorMode) {
            $(this).text('Exit Editor & Resume Play').addClass('active-editor');
            ui.editorControlsContainer.show();
            if (currentGame && currentGame.enterEditorMode) currentGame.enterEditorMode();
        } else {
            $(this).text('Enter Editor Mode').removeClass('active-editor');
            ui.editorControlsContainer.hide();
            if (currentGame && currentGame.exitEditorModeAndPlay) currentGame.exitEditorModeAndPlay();
        }
    });
    ui.editorClearBoardButton.on('click', function() {
        if (isEditorMode && currentGame && currentGame.clearEditorBoard) currentGame.clearEditorBoard();
    });
    ui.llmPlayFromPositionButton.on('click', function() {
        if (isEditorMode && currentGame && currentGame.exitEditorModeAndPlay) {
            isEditorMode = false;
            ui.toggleEditorButton.text('Enter Editor Mode').removeClass('active-editor');
            ui.editorControlsContainer.hide();
            currentGame.exitEditorModeAndPlay();
        }
    });

    // --- Reset Button & Log Toggling/Clearing ---
    ui.resetButton.on('click', function() {
        if (isEditorMode) { isEditorMode = false; ui.toggleEditorButton.text('Enter Editor Mode').removeClass('active-editor'); ui.editorControlsContainer.hide(); }
        if (currentGame && currentGame.resetGameLogic) {
            currentGame.resetGameLogic();
            conversationLogs = { player1: [], player2: [] };
            ui.llmConversationLogContainerPlayer1.hide(); ui.togglePlayer1ConversationButton.text(`View ${currentGame.player1Name}'s Convo`);
            ui.llmConversationLogContainerPlayer2.hide(); ui.togglePlayer2ConversationButton.text(`View ${currentGame.player2Name}'s Convo`);
        }
    });
    ui.togglePlayer1ConversationButton.on('click', function() {
        ui.llmConversationLogContainerPlayer1.toggle();
        $(this).text(ui.llmConversationLogContainerPlayer1.is(':visible') ? `Hide ${currentGame.player1Name}'s Convo` : `View ${currentGame.player1Name}'s Convo`);
        if (ui.llmConversationLogContainerPlayer1.is(':visible')) displayConversationLog('player1');
    });
    ui.togglePlayer2ConversationButton.on('click', function() {
        ui.llmConversationLogContainerPlayer2.toggle();
        $(this).text(ui.llmConversationLogContainerPlayer2.is(':visible') ? `Hide ${currentGame.player2Name}'s Convo` : `View ${currentGame.player2Name}'s Convo`);
        if (ui.llmConversationLogContainerPlayer2.is(':visible')) displayConversationLog('player2');
    });
    ui.clearLogButtons.on('click', function() {
        const playerToClear = $(this).data('player');
        if (conversationLogs[playerToClear]) {
            conversationLogs[playerToClear] = [];
            const logContainer = playerToClear === 'player1' ? ui.llmConversationLogContainerPlayer1 : ui.llmConversationLogContainerPlayer2;
            if (logContainer.is(':visible')) displayConversationLog(playerToClear);
        }
    });
    ui.llmPlayerControlSelect.on('change', function() {
        if (!isEditorMode && currentGame) {
            if(currentGame.updateStatusLogic) currentGame.updateStatusLogic();
            triggerLLMMoveIfNeeded();
        }
    });

    // --- Resize Observer ---
    if (window.ResizeObserver && ui.dynamicBoardContainer.length) {
        new ResizeObserver(() => { if (currentGame && currentGame.handleResize) currentGame.handleResize(); }).observe(ui.dynamicBoardContainer[0]);
    } else { $(window).resize(() => { if (currentGame && currentGame.handleResize) currentGame.handleResize(); }); }


    // --- Function to fetch and display saved board states ---
    async function fetchAndDisplaySavedStates(gameId) {
        const savedStatesContainerId = `${gameId}SavedStatesContainer`;
        // Remove previous saved states container if it exists
        $(`#${savedStatesContainerId}`).remove();

        const savedStatesContainer = $('<div>')
            .attr('id', savedStatesContainerId)
            .addClass('saved-states-area')
            .html(`<h4>Load Saved Position:</h4><select id="${gameId}SavedStatesSelect"><option value="">-- Select a position --</option></select>`);

        // Prepend to gameSpecificEditorControls so it appears before other inputs if desired
        ui.gameSpecificEditorControls.prepend(savedStatesContainer);
        const selectEl = $(`#${gameId}SavedStatesSelect`);

        try {
            // Conceptual Backend Endpoint (replace with your actual endpoint)
            // const response = await fetch(`${ui.backendUrlInput.val()}/get-saved-board-states?game=${gameId}`);
            // if (!response.ok) throw new Error('Failed to fetch saved states.');
            // const data = await response.json();

            // STUBBED DATA for now:
            let data = { savedStates: [] };
            if (gameId === 'chess') {
                data.savedStates = [
                    { name: "Queen's Gambit Declined", state: "rnbqkb1r/pp2pp1p/3p1np1/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6" }, // Example FEN
                    { name: "Sicilian Dragon, Yugoslav Attack", state: "r2qk2r/pb1nbppp/4p3/1pp1P1P1/2BP3P/2N1BN2/PP3P2/R2QK2R w KQkq - 0 14" }
                ];
            } else if (gameId === 'tictactoe') {
                data.savedStates = [
                    { name: "Center X, Corner O", state: "O___X___X" },
                    { name: "Almost Draw", state: "XOXOX_O_X" }
                ];
            }
            // END STUBBED DATA

            if (data.savedStates && data.savedStates.length > 0) {
                data.savedStates.forEach(savedState => {
                    selectEl.append($('<option>').val(savedState.state).text(savedState.name));
                });

                selectEl.on('change', function() {
                    const selectedState = $(this).val();
                    if (selectedState && currentGame && currentGame.setBoardFromEditorState) {
                        currentGame.setBoardFromEditorState(selectedState);
                        if(currentGame.updateBoardUIVisuals) currentGame.updateBoardUIVisuals(); // Ensure visuals update
                        updateDisplayElements(); // Update status and main state display
                         // Also update the manual FEN/state input field if it exists for this game
                        if (gameId === 'chess' && $('#chessEditorFenInput').length) {
                            $('#chessEditorFenInput').val(selectedState.split(' ')[0]); // Show piece part for chess
                        } else if (gameId === 'tictactoe' && $('#tttEditorBoardStateInput').length) {
                            $('#tttEditorBoardStateInput').val(selectedState);
                        }
                    }
                });
            } else {
                selectEl.replaceWith($('<p>No saved positions available for this game.</p>'));
            }
        } catch (error) {
            console.error("Error fetching or displaying saved states:", error);
            selectEl.replaceWith($('<p>Error loading saved positions.</p>'));
        }
    }


    // =======================================================================================
    // TIC-TAC-TOE SPECIFIC LOGIC
    // =======================================================================================
    function initTicTacToeModule() {
        const TTT_PLAYER_X = gamesConfig.tictactoe.player1Name;
        const TTT_PLAYER_O = gamesConfig.tictactoe.player2Name;
        const TTT_EMPTY = '_';
        let ttt_currentPlayer;
        let ttt_boardState;
        let ttt_gameActive;
        const ttt_winningConditions = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]
        ];

        function ttt_checkWin() {
            for (let i = 0; i < ttt_winningConditions.length; i++) {
                const [a, b, c] = ttt_winningConditions[i];
                if (ttt_boardState[a] !== TTT_EMPTY && ttt_boardState[a] === ttt_boardState[b] && ttt_boardState[a] === ttt_boardState[c]) {
                    return { winner: ttt_boardState[a], line: [a,b,c] };
                }
            } return null;
        }
        function ttt_checkDraw() { return !ttt_boardState.includes(TTT_EMPTY) && !ttt_checkWin(); }
        function ttt_boardStateToString(stateArray = ttt_boardState) { return stateArray.join(''); }
        function ttt_stringToBoardState(str) { return (typeof str === 'string' && str.length === 9 && /^[XO_]{9}$/.test(str.toUpperCase())) ? str.toUpperCase().split('') : Array(9).fill(TTT_EMPTY); }

        gamesConfig.tictactoe.updateBoardUIVisuals = function() {
            const boardEl = ui.dynamicBoardContainer.find('#ticTacToeBoard');
            if (!boardEl.length) return; // Board not injected yet
            boardEl.empty();
            ttt_boardState.forEach((cell, index) => {
                const cellDiv = $('<div></div>').addClass('ttt-cell').attr('data-index', index).text(cell === TTT_EMPTY ? '' : cell);
                if (cell === TTT_PLAYER_X) cellDiv.addClass('X'); if (cell === TTT_PLAYER_O) cellDiv.addClass('O');
                // Click handler is now added in initGame or enterEditorMode
                boardEl.append(cellDiv);
            });
            if (!ttt_gameActive) {
                const winInfo = ttt_checkWin();
                if (winInfo) {
                     winInfo.line.forEach(index => $('#ticTacToeBoard').find(`.ttt-cell[data-index=${index}]`).addClass('winning-cell'));
                }
            }
        };

        gamesConfig.tictactoe.updateStatusLogic = function() {
            if (!ttt_gameActive) {
                const winInfo = ttt_checkWin();
                if (winInfo) ui.statusEl.text(`${winInfo.winner} Wins!`);
                else if (ttt_checkDraw()) ui.statusEl.text("It's a Draw!");
                return;
            }
            ui.statusEl.text(`${ttt_currentPlayer} to move.`);
        };

        gamesConfig.tictactoe.initGame = function(initialBoardStr = "_________") {
            ui.dynamicBoardContainer.html('<div id="ticTacToeBoard"></div>');
            $('#ticTacToeBoard').off('click', '.ttt-cell').on('click', '.ttt-cell', function() { // Game mode click handler
                if (currentGameId === 'tictactoe') gamesConfig.tictactoe.handleCellClick($(this).data('index'));
            });
            ttt_boardState = ttt_stringToBoardState(initialBoardStr.replace(/ /g, TTT_EMPTY));
            ttt_currentPlayer = gamesConfig.tictactoe.player1Name;
            ttt_gameActive = true;
            const winInfo = ttt_checkWin(); if (winInfo) ttt_gameActive = false; else if (ttt_checkDraw()) ttt_gameActive = false;
            updateDisplayElements();
            triggerLLMMoveIfNeeded();
        };
        gamesConfig.tictactoe.resetGameLogic = function() { this.initGame("_________"); };
        gamesConfig.tictactoe.getGameStateString = () => ttt_boardStateToString();

        gamesConfig.tictactoe.isLLMsTurnLogic = function() {
            if (!ttt_gameActive || isEditorMode) return false;
            const controlMode = ui.llmPlayerControlSelect.val();
            if (controlMode === 'neither') return false; if (controlMode === 'both') return true;
            return controlMode === ttt_currentPlayer;
        };

        gamesConfig.tictactoe.handleCellClick = function(clickedIndex) {
            if (!ttt_gameActive || isEditorMode || gamesConfig.tictactoe.isLLMsTurnLogic()) return;
            if (ttt_boardState[clickedIndex] === TTT_EMPTY) {
                ttt_boardState[clickedIndex] = ttt_currentPlayer;
                const winInfo = ttt_checkWin();
                if (winInfo) ttt_gameActive = false; else if (ttt_checkDraw()) ttt_gameActive = false;
                else ttt_currentPlayer = (ttt_currentPlayer === TTT_PLAYER_X) ? TTT_PLAYER_O : TTT_PLAYER_X;
                updateDisplayElements();
                if (ttt_gameActive) triggerLLMMoveIfNeeded();
            }
        };

        gamesConfig.tictactoe.makeLLMMoveLogic = async function() {
            const llmPlayerForTurn = ttt_currentPlayer;
            const logTargetIdentifier = llmPlayerForTurn === TTT_PLAYER_X ? 'player1' : 'player2';
            if (!ttt_gameActive || !gamesConfig.tictactoe.isLLMsTurnLogic()) return;
            ui.statusEl.text(`LLM (${llmPlayerForTurn}) is thinking...`);
            let turnSpecificLog = [];
            const selectedModel = $(`input[name="${currentGameId}_model"]:checked`).val();
            const selectedPrompt = $(`input[name="${currentGameId}_prompting_method"]:checked`).val();
            let llmMoveIndex = -1;

            if (ui.useFrontendStubCheckbox.is(':checked')) {
                turnSpecificLog.push({sender: "System", type: "info", content: `Frontend LLM Stub for ${llmPlayerForTurn} (TTT).`});
                turnSpecificLog.push({sender: `LLM Stub (${llmPlayerForTurn})`, type: "input_board_state", content: ttt_boardStateToString()});
                await new Promise(resolve => setTimeout(resolve, 500 + Math.random() * 400));
                const availableCells = ttt_boardState.map((val, idx) => val === TTT_EMPTY ? idx : -1).filter(idx => idx !== -1);
                if (availableCells.length > 0) llmMoveIndex = availableCells[Math.floor(Math.random() * availableCells.length)];
                else { turnSpecificLog.push({sender: `LLM Stub (${llmPlayerForTurn})`, type: "error-log", content: "No available moves."}); }
                if(llmMoveIndex !== -1) turnSpecificLog.push({sender: `LLM Stub (${llmPlayerForTurn})`, type: "decision", content: `Decided to play at index ${llmMoveIndex}.`});
            } else {
                const backendUrl = ui.backendUrlInput.val();
                if (!backendUrl) { turnSpecificLog.push({sender:"Frontend", type:"error", content:"Backend URL missing"}); }
                else {
                    turnSpecificLog.push({sender: "Frontend", type: "request_to_backend", content: `Requesting TTT LLM move for ${llmPlayerForTurn}. Model: ${selectedModel}, Prompt: ${selectedPrompt}`});
                    turnSpecificLog.push({sender: "Frontend", type: "request_board_state", content: ttt_boardStateToString()});
                    try {
                        const response = await fetch(`${backendUrl}/get-llm-move`, {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ game_id: 'tictactoe', board_state: ttt_boardStateToString(), player_to_move: llmPlayerForTurn, selected_model_id: selectedModel, selected_prompting_method_id: selectedPrompt })
                        });
                        const data = await response.json();
                        if (data.conversationLog) turnSpecificLog = turnSpecificLog.concat(data.conversationLog);
                        if (!response.ok) { const errorMsg = data.error || `HTTP error! Status: ${response.status}`; turnSpecificLog.push({sender: "Backend", type: "error-log", content: errorMsg}); throw new Error(errorMsg); }
                        llmMoveIndex = data.move_index;
                        if (llmMoveIndex === undefined || llmMoveIndex < 0 || llmMoveIndex > 8) throw new Error("Backend returned invalid move index.");
                        turnSpecificLog.push({sender: "Backend", type: "response_to_frontend", content: `Suggests move at index: ${llmMoveIndex}`});
                    } catch (error) {
                        console.error(`Error getting TTT LLM move for ${llmPlayerForTurn}:`, error);
                        ui.statusEl.text(`Error for ${llmPlayerForTurn}: ${error.message}.`);
                        if (!turnSpecificLog.find(m => m.type && m.type.includes('error'))) {
                             turnSpecificLog.push({sender: "Frontend", type: "error-log", content: `Network/Request Error for ${llmPlayerForTurn}: ${error.message}`});
                        }
                    }
                }
            }
            if (llmMoveIndex !== -1 && ttt_boardState[llmMoveIndex] === TTT_EMPTY) {
                ttt_boardState[llmMoveIndex] = llmPlayerForTurn;
                const winInfo = ttt_checkWin(); if (winInfo) ttt_gameActive = false; else if (ttt_checkDraw()) ttt_gameActive = false;
                else ttt_currentPlayer = (llmPlayerForTurn === TTT_PLAYER_X) ? TTT_PLAYER_O : TTT_PLAYER_X;
            } else if (llmMoveIndex !== -1) {
                 turnSpecificLog.push({sender: "System", type: "error-log", content: `LLM (${llmPlayerForTurn}) chose occupied/invalid cell: ${llmMoveIndex}. State: ${ttt_boardStateToString()}`});
            } else if (ttt_gameActive) {
                 turnSpecificLog.push({sender: "System", type: "error-log", content: `LLM (${llmPlayerForTurn}) failed to provide a move.`});
            }
            conversationLogs[logTargetIdentifier].push(...turnSpecificLog);
            updateDisplayElements();
            if (ui[logTargetIdentifier === 'player1' ? 'llmConversationLogContainerPlayer1' : 'llmConversationLogContainerPlayer2'].is(':visible')) displayConversationLog(logTargetIdentifier);
        };

        gamesConfig.tictactoe.setupEditorControls = function() {
            const editorHtml = `
                <div>
                    <label>Piece to Place:</label>
                    <input type="radio" name="tttEditorPiece" id="tttEditorPieceX" value="X" checked><label for="tttEditorPieceX" class="radio-label">X</label>
                    <input type="radio" name="tttEditorPiece" id="tttEditorPieceO" value="O"><label for="tttEditorPieceO" class="radio-label">O</label>
                    <input type="radio" name="tttEditorPiece" id="tttEditorPieceEmpty" value="_"><label for="tttEditorPieceEmpty" class="radio-label">Empty</label>
                </div>
                <div class="board-state-input-area">
                    <label for="tttEditorBoardStateInput">Set Board (9 chars, e.g., X_O__XO_X):</label>
                    <input type="text" id="tttEditorBoardStateInput" maxlength="9">
                    <button id="tttEditorSetBoardStateButton">Set from State</button>
                    <p id="tttBoardStateValidationMessage" class="validation-message"></p>
                </div>`;
            ui.gameSpecificEditorControls.html(editorHtml);
            // Fetch and display saved states for TTT
            fetchAndDisplaySavedStates('tictactoe'); // NEW
            $('#tttEditorSetBoardStateButton').on('click', function() {
                const inputState = $('#tttEditorBoardStateInput').val().trim().toUpperCase().replace(/ /g, TTT_EMPTY);
                gamesConfig.tictactoe.setBoardFromEditorState(inputState, '#tttBoardStateValidationMessage');
            });
        };
        gamesConfig.tictactoe.setBoardFromEditorState = function(stateString, validationMsgSelector) { // NEW helper
            const validationMsgEl = validationMsgSelector ? $(validationMsgSelector) : $('#tttBoardStateValidationMessage'); // Default if not passed
            validationMsgEl.removeClass('success error').text('');
            if (stateString.length === 9 && /^[XO_]{9}$/.test(stateString)) {
                ttt_boardState = ttt_stringToBoardState(stateString);
                this.updateBoardUIVisuals();
                updateGameStateDisplay();
                validationMsgEl.text('Board state set!').addClass('success');
                // Sync editor input if it exists and is different
                if ($('#tttEditorBoardStateInput').val() !== stateString) {
                    $('#tttEditorBoardStateInput').val(stateString);
                }
            } else { validationMsgEl.text('Invalid state. Must be 9 chars (X, O, or _).').addClass('error'); }
        };
        gamesConfig.tictactoe.enterEditorMode = function() {
            ttt_gameActive = false;
            this.updateBoardUIVisuals();
            $('#ticTacToeBoard').off('click', '.ttt-cell').on('click', '.ttt-cell', function() {
                 if (!isEditorMode) return;
                 const clickedIndex = $(this).data('index');
                 let pieceToPlace = TTT_EMPTY;
                 if ($('#tttEditorPieceX').is(':checked')) pieceToPlace = TTT_PLAYER_X;
                 else if ($('#tttEditorPieceO').is(':checked')) pieceToPlace = TTT_PLAYER_O;
                 ttt_boardState[clickedIndex] = pieceToPlace;
                 gamesConfig.tictactoe.updateBoardUIVisuals();
                 $('#tttEditorBoardStateInput').val(ttt_boardStateToString());
                 updateGameStateDisplay();
            });
            ui.statusEl.text("Editor Mode: Click cell to place selected piece.");
            $('#tttEditorBoardStateInput').val(ttt_boardStateToString());
        };
        gamesConfig.tictactoe.exitEditorModeAndPlay = function() {
            ttt_currentPlayer = ui.editorTurnPlayer1Radio.is(':checked') ? gamesConfig.tictactoe.player1Name : gamesConfig.tictactoe.player2Name;
            ttt_gameActive = true;
            const winInfo = ttt_checkWin(); if(winInfo) ttt_gameActive = false; else if (ttt_checkDraw()) ttt_gameActive = false;
            updateDisplayElements();
            $('#ticTacToeBoard').off('click', '.ttt-cell').on('click', '.ttt-cell', function() {
                if (currentGameId === 'tictactoe') gamesConfig.tictactoe.handleCellClick($(this).data('index'));
            });
            if(ttt_gameActive) triggerLLMMoveIfNeeded();
        };
        gamesConfig.tictactoe.clearEditorBoard = function() {
            ttt_boardState = Array(9).fill(TTT_EMPTY);
            this.updateBoardUIVisuals();
            $('#tttEditorBoardStateInput').val(ttt_boardStateToString());
            updateGameStateDisplay();
        };
    }

    // =======================================================================================
    // CHESS SPECIFIC LOGIC
    // =======================================================================================
    function initChessModule() {
        let chess_game;
        let chess_board_ui;
        const CHESS_PLAYER1 = gamesConfig.chess.player1Name.toLowerCase();
        const CHESS_PLAYER2 = gamesConfig.chess.player2Name.toLowerCase();
        const chess_pieceThemeUrl = 'chess/img/chesspieces/alpha/{piece}.png';

        gamesConfig.chess.updateBoardUIVisuals = function() {
            if (chess_board_ui && chess_game) {
                chess_board_ui.position(chess_game.fen());
            }
        };

        gamesConfig.chess.initGame = function(fen = 'start') { // Ensure 'start' is default
            if (typeof Chess === "undefined" || typeof Chessboard === "undefined") {
                ui.dynamicBoardContainer.html("<p>Loading Chess components...</p>");
                loadGameAssets('chess', () => this.initGame(fen));
                return;
            }
            fen = fen == 'start' || fen == '' ? 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1' : fen.trim(); // Ensure valid FEN or default to 'start'
            console.log(`Initializing Chess game with FEN: ${fen}`);
            chess_game = new Chess(fen); // Uses 'start' by default from chess.js if fen is 'start'
            if (chess_board_ui) chess_board_ui.destroy();
            ui.dynamicBoardContainer.html('<div id="chessBoardUiElement" style="width:100%; max-width:400px;"></div>');

            const config = {
                draggable: true, position: chess_game.fen(), pieceTheme: chess_pieceThemeUrl,
                onDragStart: (source, piece) => {
                    if (!currentGame || currentGameId !== 'chess' || isEditorMode || chess_game.game_over()) return false;
                    if ((chess_game.turn() === 'w' && piece.search(/^b/) !== -1) || (chess_game.turn() === 'b' && piece.search(/^w/) !== -1)) return false;
                    const controlMode = ui.llmPlayerControlSelect.val();
                    if (controlMode === 'both') return false;
                    if (controlMode === CHESS_PLAYER1 && chess_game.turn() === 'w') return false;
                    if (controlMode === CHESS_PLAYER2 && chess_game.turn() === 'b') return false;
                    return true;
                },
                onDrop: (source, target) => {
                    if (isEditorMode) return;
                    const move = chess_game.move({ from: source, to: target, promotion: 'q' });
                    if (move === null) return 'snapback';
                    updateDisplayElements();
                    triggerLLMMoveIfNeeded();
                },
                onSnapEnd: () => { if(!isEditorMode && chess_board_ui) gamesConfig.chess.updateBoardUIVisuals(); }
            };
            chess_board_ui = Chessboard('chessBoardUiElement', config);
            updateDisplayElements();
            triggerLLMMoveIfNeeded();
        };
        gamesConfig.chess.resetGameLogic = function() { this.initGame('start'); }; // Explicitly reset to 'start'
        gamesConfig.chess.getGameStateString = () => chess_game ? chess_game.fen() : 'Chess not initialized';
        gamesConfig.chess.updateStatusLogic = function() {
            if (!chess_game) { ui.statusEl.text("Chess game not loaded."); return;}
            let statusText = '';
            const moveColor = chess_game.turn() === 'w' ? gamesConfig.chess.player1Name : gamesConfig.chess.player2Name;
            if (chess_game.game_over()) {
                if (chess_game.in_checkmate()) statusText = `CHECKMATE! ${moveColor === gamesConfig.chess.player1Name ? gamesConfig.chess.player2Name : gamesConfig.chess.player1Name} wins.`;
                else if (chess_game.in_draw()) statusText = 'DRAW.'; else if (chess_game.in_stalemate()) statusText = 'STALEMATE.';
                else statusText = 'GAME OVER.';
            } else { statusText = `${moveColor} to move.`; if (chess_game.in_check()) statusText += ` ${moveColor} is in check.`;}
            ui.statusEl.text(statusText);
        };
        gamesConfig.chess.isLLMsTurnLogic = function() {
            if (!chess_game || chess_game.game_over() || isEditorMode) return false;
            const controlMode = ui.llmPlayerControlSelect.val();
            if (controlMode === 'neither') return false; if (controlMode === 'both') return true;
            const currentTurnColor = chess_game.turn() === 'w' ? CHESS_PLAYER1 : CHESS_PLAYER2;
            return controlMode === currentTurnColor;
        };
        gamesConfig.chess.makeLLMMoveLogic = async function() {
            if (!chess_game || !gamesConfig.chess.isLLMsTurnLogic()) return;
            const llmPlayerForTurnColor = chess_game.turn() === 'w' ? CHESS_PLAYER1 : CHESS_PLAYER2;
            const logTargetIdentifier = chess_game.turn() === 'w' ? 'player1' : 'player2';
            ui.statusEl.text(`LLM (${llmPlayerForTurnColor}) is thinking...`);
            let turnSpecificLog = [];
            const selectedModel = $(`input[name="${currentGameId}_model"]:checked`).val();
            const selectedPrompt = $(`input[name="${currentGameId}_prompting_method"]:checked`).val();
            let llmMoveData = null;

            if (ui.useFrontendStubCheckbox.is(':checked')) {
                turnSpecificLog.push({sender: "System", type: "info", content: `Frontend LLM Stub for ${llmPlayerForTurnColor} (Chess).`});
                turnSpecificLog.push({sender: `LLM Stub (${llmPlayerForTurnColor})`, type: "input_fen", content: chess_game.fen()});
                await new Promise(resolve => setTimeout(resolve, 700 + Math.random() * 500));
                const possibleMoves = chess_game.moves({verbose: true});
                if (possibleMoves.length > 0) llmMoveData = possibleMoves[Math.floor(Math.random() * possibleMoves.length)].san;
                else { turnSpecificLog.push({sender: `LLM Stub (${llmPlayerForTurnColor})`, type: "error-log", content: "No legal moves."}); }
                if(llmMoveData) turnSpecificLog.push({sender: `LLM Stub (${llmPlayerForTurnColor})`, type: "decision", content: `Decided to play ${llmMoveData}.`});
            } else {
                const backendUrl = ui.backendUrlInput.val();
                if (!backendUrl) { turnSpecificLog.push({sender:"Frontend", type:"error", content:"Backend URL missing"}); }
                 else {
                    turnSpecificLog.push({sender: "Frontend", type: "request_to_backend", content: `Requesting Chess LLM move for ${llmPlayerForTurnColor}. Model: ${selectedModel}, Prompt: ${selectedPrompt}`});
                    turnSpecificLog.push({sender: "Frontend", type: "request_fen", content: chess_game.fen()});
                    try {
                        const response = await fetch(`${backendUrl}/get-llm-move`, {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ game_id: 'chess', fen: chess_game.fen(), player_to_move: llmPlayerForTurnColor, selected_model_id: selectedModel, selected_prompting_method_id: selectedPrompt })
                        });
                        const data = await response.json();
                        if (data.conversationLog) turnSpecificLog = turnSpecificLog.concat(data.conversationLog);
                        if (!response.ok) { const errorMsg = data.error || `HTTP error! Status: ${response.status}`; turnSpecificLog.push({sender: "Backend", type: "error-log", content: errorMsg}); throw new Error(errorMsg); }
                        llmMoveData = data.move;
                        if (!llmMoveData) throw new Error("Backend returned no move.");
                        turnSpecificLog.push({sender: "Backend", type: "response_to_frontend", content: `Suggests move: ${llmMoveData}`});
                    } catch (error) {
                         console.error(`Error getting Chess LLM move for ${llmPlayerForTurnColor}:`, error);
                        ui.statusEl.text(`Error for ${llmPlayerForTurnColor}: ${error.message}.`);
                        if (!turnSpecificLog.find(m => m.type && m.type.includes('error'))) {
                             turnSpecificLog.push({sender: "Frontend", type: "error-log", content: `Network/Request Error for ${llmPlayerForTurnColor}: ${error.message}`});
                        }
                    }
                }
            }
            if (llmMoveData) { const moveResult = chess_game.move(llmMoveData, { sloppy: true }); if (!moveResult) { turnSpecificLog.push({sender: "System", type: "error-log", content: `LLM (${llmPlayerForTurnColor}) chose invalid move: ${llmMoveData}.`});}}
            else if(chess_game.game_over() == false) { turnSpecificLog.push({sender: "System", type: "error-log", content: `LLM (${llmPlayerForTurnColor}) failed to provide a move.`}); }
            conversationLogs[logTargetIdentifier].push(...turnSpecificLog);
            updateDisplayElements();
            if (ui[logTargetIdentifier === 'player1' ? 'llmConversationLogContainerPlayer1' : 'llmConversationLogContainerPlayer2'].is(':visible')) displayConversationLog(logTargetIdentifier);
        };

        gamesConfig.chess.setupEditorControls = function() {
            const editorHtml = `
                <button id="chessEditorStartPosition">Start Position</button>
                <button id="chessEditorFlipBoard">Flip Orientation</button>
                <div class="fen-input-area">
                    <label for="chessEditorFenInput">Set Board from FEN:</label>
                    <input type="text" id="chessEditorFenInput">
                    <button id="chessEditorSetFenButton">Set from FEN</button>
                    <p id="chessFenValidationMessage" class="validation-message"></p>
                </div>
                <div id="chessSavedStatesContainerPlaceholder"></div> <!-- Placeholder for saved states -->
                `;
            ui.gameSpecificEditorControls.html(editorHtml);
             // Fetch and display saved states for Chess
            fetchAndDisplaySavedStates('chess'); // NEW
            $('#chessEditorStartPosition').on('click', gamesConfig.chess.startPositionEditor);
            $('#chessEditorFlipBoard').on('click', gamesConfig.chess.flipBoardEditor);
            $('#chessEditorSetFenButton').on('click', function() {
                const fen = $('#chessEditorFenInput').val().trim();
                gamesConfig.chess.setBoardFromEditorState(fen, '#chessFenValidationMessage');
            });
        };
         gamesConfig.chess.setBoardFromEditorState = function(fen, validationMsgSelector) { // NEW Helper
            const validationMsgEl = validationMsgSelector ? $(validationMsgSelector) : $('#chessFenValidationMessage');
            validationMsgEl.removeClass('success error').text('');
            const tempGame = new Chess();
            if (tempGame.load(fen)) {
                chess_game.load(fen);
                this.updateBoardUIVisuals();
                if (chess_game.turn() === 'w') ui.editorTurnPlayer1Radio.prop('checked', true); else ui.editorTurnPlayer2Radio.prop('checked', true);
                updateDisplayElements(); validationMsgEl.text('FEN set successfully!').addClass('success');
                // Sync editor input if it exists and is different
                if ($('#chessEditorFenInput').val() !== fen) {
                     $('#chessEditorFenInput').val(fen); // Show full FEN
                }
            } else { validationMsgEl.text(`Invalid FEN: ${tempGame.validate_fen(fen).error || 'Unknown reason'}`).addClass('error');}
        };
        gamesConfig.chess.enterEditorMode = function() {
            if (!chess_board_ui) { this.initGame(chess_game ? chess_game.fen() : 'start'); }
            chess_board_ui.draggable(true); chess_board_ui.dropOffBoard('trash'); chess_board_ui.sparePieces(true);
            // Detach previous game-mode drop handler and attach editor-mode drop handler
            chess_board_ui.off('drop'); // Remove previous onDrop
            chess_board_ui.on('drop', function(source, target, piece, newPosFenObj, oldPosFenObj) {
                if (isEditorMode) {
                     const boardFenOnly = Chessboard.objToFen(newPosFenObj);
                     $('#chessEditorFenInput').val(boardFenOnly);
                     ui.currentGameStateDisplay.val(boardFenOnly + " (Editor: pieces only)");
                     // Update chess_game with piece placement for consistency if FEN input is used later
                     const currentTurnEditor = ui.editorTurnPlayer1Radio.is(':checked') ? 'w' : 'b';
                     chess_game.load(boardFenOnly + " " + currentTurnEditor + " - - 0 1");
                }
            });
            ui.statusEl.text("Editor Mode: Setup board, then Exit or Play.");
            $('#chessEditorFenInput').val(chess_board_ui.fen());
        };
        gamesConfig.chess.exitEditorModeAndPlay = function() {
            const editorFenPieces = chess_board_ui ? chess_board_ui.fen() : chess_game.fen().split(' ')[0];
            const editorTurn = ui.editorTurnPlayer1Radio.is(':checked') ? 'w' : 'b';
            const fullEditorFen = `${editorFenPieces} ${editorTurn} - - 0 1`;
            this.initGame(fullEditorFen);
        };
        gamesConfig.chess.clearEditorBoard = function() {
            if (chess_board_ui) chess_board_ui.clear(false);
            // chess_game.load('8/8/8/8/8/8/8/8 w - - 0 1');
            chess_game.load('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
            $('#chessEditorFenInput').val(chess_board_ui ? chess_board_ui.fen() : '');
            updateDisplayElements();
        };
        gamesConfig.chess.startPositionEditor = function() {
            // const startFen = new Chess().fen(); // Standard start FEN
            const startFen = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
            if (chess_board_ui) chess_board_ui.position(startFen, false); // Update visual
            chess_game.load(startFen); // Update logic
            $('#chessEditorFenInput').val(startFen.split(' ')[0]); // Show piece part
            if (chess_game.turn() === 'w') ui.editorTurnPlayer1Radio.prop('checked', true); else ui.editorTurnPlayer2Radio.prop('checked', true);
            updateDisplayElements();
        };
        gamesConfig.chess.flipBoardEditor = function() { if (chess_board_ui) chess_board_ui.flip(); };
        gamesConfig.chess.handleResize = function() { if (chess_board_ui) chess_board_ui.resize(); };

    }

    // =======================================================================================
    // APP INITIALIZATION
    // =======================================================================================
    function initializeApp() {
        initTicTacToeModule();
        initChessModule();
        ui.gameSelector.on('change', function() { switchGame($(this).val()); });
        switchGame(ui.gameSelector.val());
    }
    initializeApp();
});