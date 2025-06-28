$(document).ready(function() {
    // --- Global State & Configuration ---
    let currentGameId = null; 
    let currentGame = null;   
    let isEditorMode = false;
    
    // History and Navigation State
    let gameHistory = []; // Array of {state: string, move: object, conversation: {player1: [], player2: []}}
    let historyPointer = -1; // Points to the current state in gameHistory. -1 means before the first move.
    let isAutoPlaying = false;
    let autoPlayInterval = null;

    // --- Saved States ---
    const PERSISTENT_SAVED_STATES = {
        chess: [
            { name: "Start Position", state: "start" },
            { name: "Queen's Gambit Declined", state: "rnbqkb1r/pp2pp1p/3p1np1/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6" },
            { name: "Sicilian Dragon, Yugoslav Attack", state: "r2qk2r/pb1nbppp/4p3/1pp1P1P1/2BP3P/2N1BN2/PP3P2/R2QK2R w KQkq - 0 14" }
        ],
        tictactoe: [
            { name: "Empty Board", state: "_________" },
            { name: "Center X, Corner O", state: "O___X___X" },
            { name: "Almost Draw", state: "XOXOX_O_X" }
        ]
    };
    let savedStates = JSON.parse(JSON.stringify(PERSISTENT_SAVED_STATES));


    // --- UI Elements Cache (Common) ---
    const ui = {
        gameSelector: $('#gameSelector'),
        dynamicBoardContainer: $('#dynamicBoardContainer'),
        statusEl: $('#status'),
        gameStateLabel: $('#gameStateLabel'),
        currentGameStateDisplay: $('#currentGameStateDisplay'),
        useFrontendStubCheckbox: $('#useFrontendStub'),
        backendUrlInput: $('#backendUrl'),
        navReset: $('#navReset'),
        navBack: $('#navBack'),
        navPlayPause: $('#navPlayPause'),
        navForward: $('#navForward'),
        playIcon: $('#navPlayPause .play-icon'), // More specific selector
        pauseIcon: $('#navPlayPause .pause-icon'), // More specific selector
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
            makeLLMMoveLogic: null, resetGameLogic: null, setupEditorControls: null,
            setBoardFromEditorState: null, clearEditorBoard: null, updateBoardUIVisuals: null,
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
                // FIX: Correct, stable URL for chess.js
                js: [ 'https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js',
                      'https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js' ],
                css: [ 'https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css' ]
            },
            initGame: null, getGameStateString: null, isLLMsTurnLogic: null, makeLLMMoveLogic: null,
            resetGameLogic: null, setupEditorControls: null,
            setBoardFromEditorState: null, clearEditorBoard: null,
            flipBoardEditor: null, startPositionEditor: null, updateBoardUIVisuals: null,
            handleResize: null,
            getLLMPlayerControlOptions: function() {
                 return [
                    { value: 'black', text: `${this.player2Name}` },
                    { value: 'white', text: `${this.player1Name}` },
                    { value: 'both', text: `Both ${this.player1Name} & ${this.player2Name}` },
                    { value: 'neither', text: `Neither (Human vs Human)` }
                ];
            }
        }
    };

    function loadGameAssets(gameId, callback) {
        const assets = gamesConfig[gameId].assets;
        let jsToLoad = assets.js.length;
        if (jsToLoad === 0) { if(callback) callback(); return; }
        assets.css.forEach(url => loadCSS(url));
        assets.js.forEach(url => {
            loadScript(url, () => { jsToLoad--; if (jsToLoad === 0) { if (callback) callback(); } });
        });
    }

    function switchGame(newGameId) {
        if (currentGameId === newGameId && currentGame) return;
        stopAutoPlay();
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

        loadGameAssets(newGameId, () => {
            console.log(`${currentGame.name} assets loaded. Initializing game.`);
            isEditorMode = false;
            ui.editorControlsContainer.hide();
            ui.toggleEditorButton.text('Enter Editor Mode').removeClass('active-editor');
            ui.gameSpecificEditorControls.empty();
            if (currentGame.setupEditorControls) currentGame.setupEditorControls();

            if (currentGame.initGame) {
                currentGame.initGame();
            } else {
                console.error(`initGame function not defined for ${newGameId}`);
            }
            fetchLLMSettingsOptions();
        });
    }

    function updateStatus() { if (currentGame && currentGame.updateStatusLogic) currentGame.updateStatusLogic(); }
    function updateGameStateDisplay() { if (currentGame && currentGame.getGameStateString) ui.currentGameStateDisplay.val(currentGame.getGameStateString());}

    function updateDisplayForCurrentHistory() {
        if (!currentGame) return;
        const currentHistoryEntry = gameHistory[historyPointer] || currentGame.getInitialHistoryEntry();

        currentGame.loadState(currentHistoryEntry.state);

        updateStatus();
        updateGameStateDisplay();
        updateNavButtons();

        displayConversationLog('player1');
        displayConversationLog('player2');
    }

    function displayConversationLog(playerIdentifier) {
        if (!currentGame) return;
        const currentHistoryEntry = gameHistory[historyPointer];
        const playerLogData = currentHistoryEntry ? currentHistoryEntry.conversation[playerIdentifier] : [];
        const logEl = playerIdentifier === 'player1' ? ui.llmConversationLogPlayer1El : ui.llmConversationLogPlayer2El;

        logEl.empty();
        if (!playerLogData || playerLogData.length === 0) {
            logEl.append($('<p>No conversation for this turn.</p>'));
            return;
        }
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

    async function fetchLLMSettingsOptions() { /* ... (Same as before) ... */ }
    ui.backendUrlInput.on('change', fetchLLMSettingsOptions);

    async function makeLLMMove() {
        if (!currentGame || !currentGame.makeLLMMoveLogic || isEditorMode) return Promise.resolve();

        return currentGame.makeLLMMoveLogic().then(newHistoryData => {
            if (newHistoryData) {
                addHistoryEntry(newHistoryData);
            }
            updateDisplayForCurrentHistory();
            triggerLLMMoveIfNeeded();
        });
    }

    function triggerLLMMoveIfNeeded() {
        if (isAutoPlaying && currentGame && currentGame.isLLMsTurnLogic && currentGame.isLLMsTurnLogic()) {
            autoPlayInterval = setTimeout(makeLLMMove, 1200);
        }
    }

    function addHistoryEntry(newEntryData) {
        if (historyPointer < gameHistory.length - 1) {
            gameHistory = gameHistory.slice(0, historyPointer + 1);
        }
        gameHistory.push(newEntryData);
        historyPointer++;
    }

    function updateNavButtons() {
        ui.navReset.prop('disabled', historyPointer <= 0);
        ui.navBack.prop('disabled', historyPointer <= 0);
        ui.navForward.prop('disabled', historyPointer >= gameHistory.length - 1);

        if (isAutoPlaying) {
            ui.navPlayPause.addClass('playing');
            ui.playIcon.hide();
            ui.pauseIcon.show();
        } else {
            ui.navPlayPause.removeClass('playing');
            ui.playIcon.show();
            ui.pauseIcon.hide();
        }
    }

    function stopAutoPlay() {
        if (isAutoPlaying) {
            isAutoPlaying = false;
            clearInterval(autoPlayInterval);
            autoPlayInterval = null;
            updateNavButtons();
        }
    }

    ui.navReset.on('click', function() {
        stopAutoPlay();
        historyPointer = 0;
        updateDisplayForCurrentHistory();
    });

    ui.navBack.on('click', function() {
        stopAutoPlay();
        if (historyPointer > 0) {
            historyPointer--;
            updateDisplayForCurrentHistory();
        }
    });

    ui.navForward.on('click', async function() {
        stopAutoPlay();
        if (historyPointer < gameHistory.length - 1) {
            historyPointer++;
            updateDisplayForCurrentHistory();
        } else if (currentGame && currentGame.isLLMsTurnLogic && currentGame.isLLMsTurnLogic()) {
            await makeLLMMove();
        }
    });

    ui.navPlayPause.on('click', function() {
        isAutoPlaying = !isAutoPlaying;
        updateNavButtons();
        if (isAutoPlaying) {
            triggerLLMMoveIfNeeded();
        } else {
            clearInterval(autoPlayInterval);
            autoPlayInterval = null;
        }
    });

    ui.toggleEditorButton.on('click', function() {
        stopAutoPlay();
        isEditorMode = !isEditorMode;
        if (isEditorMode) {
            $(this).text('Exit Editor').addClass('active-editor');
            ui.editorControlsContainer.show();
            if (currentGame && currentGame.enterEditorMode) currentGame.enterEditorMode();
        } else {
            $(this).text('Enter Editor Mode').removeClass('active-editor');
            ui.editorControlsContainer.hide();
            if (currentGame && currentGame.exitEditorModeAndPlay) currentGame.exitEditorModeAndPlay();
        }
    });
    ui.editorClearBoardButton.on('click', function() { if (isEditorMode && currentGame && currentGame.clearEditorBoard) currentGame.clearEditorBoard(); });
    ui.llmPlayFromPositionButton.on('click', function() {
        if (isEditorMode && currentGame && currentGame.exitEditorModeAndPlay) {
            isEditorMode = false;
            ui.toggleEditorButton.text('Enter Editor Mode').removeClass('active-editor');
            ui.editorControlsContainer.hide();
            currentGame.exitEditorModeAndPlay();
        }
    });

    ui.togglePlayer1ConversationButton.on('click', function() {
        ui.llmConversationLogContainerPlayer1.toggle();
        $(this).text(ui.llmConversationLogContainerPlayer1.is(':visible') ? `Hide ${currentGame.player1Name}'s Convo` : `View ${currentGame.player1Name}'s Convo`);
    });
    ui.togglePlayer2ConversationButton.on('click', function() {
        ui.llmConversationLogContainerPlayer2.toggle();
        $(this).text(ui.llmConversationLogContainerPlayer2.is(':visible') ? `Hide ${currentGame.player2Name}'s Convo` : `View ${currentGame.player2Name}'s Convo`);
    });

    ui.llmPlayerControlSelect.on('change', function() {
        if (!isEditorMode && currentGame) {
            if(currentGame.updateStatusLogic) currentGame.updateStatusLogic();
            triggerLLMMoveIfNeeded();
        }
    });

    if (window.ResizeObserver && ui.dynamicBoardContainer.length) {
        new ResizeObserver(() => { if (currentGame && currentGame.handleResize) currentGame.handleResize(); }).observe(ui.dynamicBoardContainer[0]);
    } else { $(window).resize(() => { if (currentGame && currentGame.handleResize) currentGame.handleResize(); }); }

    function populateSavedStates(gameId) { /* ... (Same as before) ... */ }

    // =======================================================================================
    // TIC-TAC-TOE SPECIFIC LOGIC
    // =======================================================================================
    function initTicTacToeModule() {
        const TTT_PLAYER_X = gamesConfig.tictactoe.player1Name;
        const TTT_PLAYER_O = gamesConfig.tictactoe.player2Name;
        const TTT_EMPTY = '_';
        let ttt_game; // This will hold the logical state { boardState, currentPlayer, gameActive }

        const ttt_winningConditions = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]
        ];

        function ttt_checkWin(boardState) {
            for (let i = 0; i < ttt_winningConditions.length; i++) {
                const [a, b, c] = ttt_winningConditions[i];
                if (boardState[a] !== TTT_EMPTY && boardState[a] === boardState[b] && boardState[a] === boardState[c]) {
                    return { winner: boardState[a], line: [a,b,c] };
                }
            } return null;
        }
        function ttt_checkDraw(boardState) { return !boardState.includes(TTT_EMPTY) && !ttt_checkWin(boardState); }
        function ttt_boardStateToString(stateArray) { return stateArray.join(''); }
        function ttt_stringToBoardState(str) { return (typeof str === 'string' && str.length === 9 && /^[XO_]{9}$/.test(str.toUpperCase())) ? str.toUpperCase().split('') : Array(9).fill(TTT_EMPTY); }

        gamesConfig.tictactoe.getInitialHistoryEntry = () => ({ state: "_________", move: null, conversation: { player1: [], player2: [] } });

        gamesConfig.tictactoe.loadState = function(stateString) {
            const boardState = ttt_stringToBoardState(stateString);
            const xCount = boardState.filter(c => c === TTT_PLAYER_X).length;
            const oCount = boardState.filter(c => c === TTT_PLAYER_O).length;

            ttt_game = {
                boardState: boardState,
                currentPlayer: xCount <= oCount ? TTT_PLAYER_X : TTT_PLAYER_O,
                gameActive: true
            };
            const winInfo = ttt_checkWin(ttt_game.boardState);
            if (winInfo || ttt_checkDraw(ttt_game.boardState)) {
                ttt_game.gameActive = false;
            }
            this.updateBoardUIVisuals();
        };

        gamesConfig.tictactoe.updateBoardUIVisuals = function() {
            const boardEl = ui.dynamicBoardContainer.find('#ticTacToeBoard');
            if (!boardEl.length || !ttt_game) return;

            // FIX: Ensure cells are created if they don't exist
            if (boardEl.children().length === 0) {
                 for (let i = 0; i < 9; i++) {
                    boardEl.append($('<div>').addClass('ttt-cell').attr('data-index', i));
                 }
                 // Re-add click handler after creating cells
                 boardEl.off('click', '.ttt-cell').on('click', '.ttt-cell', function() {
                    if (currentGameId === 'tictactoe') gamesConfig.tictactoe.handleCellClick($(this).data('index'));
                });
            }

            // Update existing cells
            boardEl.children().each(function(index) {
                const cell = ttt_game.boardState[index];
                $(this).text(cell === TTT_EMPTY ? '' : cell)
                       .removeClass('X O winning-cell')
                       .addClass(cell);
            });

            if (!ttt_game.gameActive) {
                const winInfo = ttt_checkWin(ttt_game.boardState);
                if (winInfo) {
                     winInfo.line.forEach(index => $('#ticTacToeBoard').find(`.ttt-cell[data-index=${index}]`).addClass('winning-cell'));
                }
            }
        };

        gamesConfig.tictactoe.updateStatusLogic = function() {
            if (!ttt_game) return;
            if (!ttt_game.gameActive) {
                const winInfo = ttt_checkWin(ttt_game.boardState);
                if (winInfo) ui.statusEl.text(`${winInfo.winner} Wins!`);
                else if (ttt_checkDraw(ttt_game.boardState)) ui.statusEl.text("It's a Draw!");
                return;
            }
            ui.statusEl.text(`${ttt_game.currentPlayer} to move.`);
        };

        gamesConfig.tictactoe.initGame = function() {
            ui.dynamicBoardContainer.html('<div id="ticTacToeBoard"></div>');
            gameHistory = [this.getInitialHistoryEntry()];
            historyPointer = 0;
            updateDisplayForCurrentHistory();
            triggerLLMMoveIfNeeded();
        };
        gamesConfig.tictactoe.resetGameLogic = function() { this.initGame(); };
        gamesConfig.tictactoe.getGameStateString = () => ttt_game ? ttt_boardStateToString(ttt_game.boardState) : '...';

        gamesConfig.tictactoe.isLLMsTurnLogic = function() {
            if (!ttt_game || !ttt_game.gameActive || isEditorMode) return false;
            const controlMode = ui.llmPlayerControlSelect.val();
            if (controlMode === 'neither') return false; if (controlMode === 'both') return true;
            return controlMode === ttt_game.currentPlayer;
        };

        gamesConfig.tictactoe.handleCellClick = function(clickedIndex) {
            if (!ttt_game || !ttt_game.gameActive || isEditorMode || this.isLLMsTurnLogic()) return;
            if (ttt_game.boardState[clickedIndex] === TTT_EMPTY) {
                const newBoardState = [...ttt_game.boardState];
                newBoardState[clickedIndex] = ttt_game.currentPlayer;

                const newHistoryEntry = {
                    state: newBoardState.join(''),
                    move: { player: ttt_game.currentPlayer, index: clickedIndex },
                    conversation: { player1: [], player2: [] }
                };
                addHistoryEntry(newHistoryEntry);
                updateDisplayForCurrentHistory();
                triggerLLMMoveIfNeeded();
            }
        };

        gamesConfig.tictactoe.makeLLMMoveLogic = async function() { /* ... (Same as before) ... */ };
        gamesConfig.tictactoe.setupEditorControls = function() { /* ... (Same as before) ... */ };
        gamesConfig.tictactoe.setBoardFromEditorState = function(stateString) { /* ... (Same as before) ... */ };
        gamesConfig.tictactoe.enterEditorMode = function() { /* ... (Same as before) ... */ };
        gamesConfig.tictactoe.exitEditorModeAndPlay = function() { /* ... (Same as before) ... */ };
        gamesConfig.tictactoe.clearEditorBoard = function() { /* ... (Same as before) ... */ };
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

        gamesConfig.chess.getInitialHistoryEntry = () => ({ state: "start", move: null, conversation: { player1: [], player2: [] } });

        gamesConfig.chess.loadState = function(fen) {
            if (typeof Chess === "undefined") return;
            chess_game = new Chess(fen);
            this.updateBoardUIVisuals();
        };

        gamesConfig.chess.updateBoardUIVisuals = function() {
            if (chess_board_ui && chess_game) {
                chess_board_ui.position(chess_game.fen());
            }
        };

        gamesConfig.chess.initGame = function(fen = 'start') {
            if (typeof Chess === "undefined" || typeof Chessboard === "undefined") {
                ui.dynamicBoardContainer.html("<p>Loading Chess components...</p>");
                loadGameAssets('chess', () => this.initGame(fen));
                return;
            }
            if (chess_board_ui) chess_board_ui.destroy();
            ui.dynamicBoardContainer.html('<div id="chessBoardUiElement" style="width:100%; max-width:400px;"></div>');

            const config = {
                draggable: true, position: 'start', pieceTheme: chess_pieceThemeUrl, // Always init with start visually
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
                    const move = { from: source, to: target, promotion: 'q' };
                    const result = chess_game.move(move);
                    if (result === null) return 'snapback';

                    const newHistoryEntry = {
                        state: chess_game.fen(),
                        move: result, // The move object from chess.js
                        conversation: { player1: [], player2: [] }
                    };
                    addHistoryEntry(newHistoryEntry);
                    updateDisplayForCurrentHistory();
                    triggerLLMMoveIfNeeded();
                },
                onSnapEnd: () => { if(!isEditorMode && chess_board_ui) gamesConfig.chess.updateBoardUIVisuals(); } 
            };
            chess_board_ui = Chessboard('chessBoardUiElement', config); 
            gameHistory = [this.getInitialHistoryEntry()];
            historyPointer = 0;
            updateDisplayForCurrentHistory();
            triggerLLMMoveIfNeeded();
        };
        // ... (All other chess functions refactored to work with the history model) ...
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
