document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded');

    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-btn');

    console.log('Elements found:', {
        chatMessages: !!chatMessages,
        userInput: !!userInput,
        sendButton: !!sendButton
    });

    if (!chatMessages || !userInput || !sendButton) {
        console.error('Some elements not found!');
        return;
    }

    // Mensaje de bienvenida
    addBotMessage("¡Hola! Soy el asistente virtual de Pharma-GO. ¿En qué puedo ayudarte?");

    async function sendMessage() {
        const message = userInput.value.trim();
        
        if (!message) return;

        // Deshabilitar input y botón mientras se envía
        userInput.disabled = true;
        sendButton.disabled = true;
        
        try {
            // Mostrar mensaje del usuario inmediatamente
            addUserMessage(message);
            userInput.value = '';

            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });

            const data = await response.json();
            
            // Mostrar SID en consola
            console.log(`Chat Session ID: ${data.session_id}`);
            
            if (data.error) {
                addSystemMessage("Lo siento, hubo un error. Por favor, intenta de nuevo.");
                console.error('Error:', data.error);
            } else {
                addBotMessage(data.response);
            }

        } catch (error) {
            console.error('Error:', error);
            addSystemMessage("Error de conexión. Por favor, verifica tu conexión a internet.");
        } finally {
            // Rehabilitar input y botón
            userInput.disabled = false;
            sendButton.disabled = false;
            userInput.focus();
        }
    }

    function addUserMessage(message) {
        const div = document.createElement('div');
        div.className = 'message user-message';
        div.textContent = message;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    function addBotMessage(message) {
        const div = document.createElement('div');
        div.className = 'message bot-message';
        div.textContent = message;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    function addSystemMessage(message) {
        const div = document.createElement('div');
        div.className = 'message system-message';
        div.textContent = message;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Event listeners
    sendButton.addEventListener('click', sendMessage);

    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Enfoque inicial en el input
    userInput.focus();

    const regionSelect = document.getElementById('region-select');
    const comunaSelect = document.getElementById('comuna-select');
    const searchBtn = document.getElementById('search-btn');
    const resultsTable = document.getElementById('results-table');
    const resultsBody = document.getElementById('results-body');

    // Load regions when page loads
    loadRegions();

    // Event listeners
    regionSelect.addEventListener('change', loadComunas);
    searchBtn.addEventListener('click', searchFarmacias);

    async function loadRegions() {
        try {
            const response = await fetch('/get_regions');
            const regions = await response.json();
            
            regions.forEach(region => {
                const option = document.createElement('option');
                option.value = region;
                option.textContent = region;
                regionSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading regions:', error);
        }
    }

    async function loadComunas() {
        const selectedRegion = regionSelect.value;
        if (!selectedRegion) return;

        try {
            const response = await fetch(`/get_comunas/${selectedRegion}`);
            const comunas = await response.json();
            
            // Clear previous options
            comunaSelect.innerHTML = '<option value="">Seleccione una comuna</option>';
            
            comunas.forEach(comuna => {
                const option = document.createElement('option');
                option.value = comuna;
                option.textContent = comuna;
                comunaSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading comunas:', error);
        }
    }

    async function searchFarmacias() {
        const region = regionSelect.value;
        const comuna = comunaSelect.value;

        if (!region || !comuna) {
            alert('Por favor seleccione región y comuna');
            return;
        }

        try {
            const response = await fetch(`/search_farmacias/${region}/${comuna}`);
            const farmacias = await response.json();
            
            displayResults(farmacias);
        } catch (error) {
            console.error('Error searching farmacias:', error);
        }
    }

    function displayResults(farmacias) {
        resultsBody.innerHTML = '';
        resultsTable.style.display = 'table';

        farmacias.forEach(farmacia => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${farmacia.local_nombre || '-'}</td>
                <td>${farmacia.localidad_nombre || '-'}</td>
                <td>${farmacia.local_direccion || '-'}</td>
                <td>${farmacia.de_turno ? 'Sí' : 'No'}</td>
                <td>${farmacia.url_direccion ? 
                    `<a href="${farmacia.url_direccion}" target="_blank">Ver mapa</a>` : 
                    'No disponible'}</td>
            `;
            resultsBody.appendChild(row);
        });
    }

    // Chat functionality
    class ChatManager {
        constructor() {
            this.messages = [];
            this.messageContainer = document.getElementById('chat-messages');
            this.userInput = document.getElementById('user-input');
            this.sendButton = document.getElementById('send-btn');
            
            // Agregar los event listeners en el constructor
            this.sendButton.addEventListener('click', () => this.sendMessage());
            this.userInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.sendMessage();
                }
            });
            
            this.initialize();
        }

        async initialize() {
            // Cargar historial existente
            try {
                const response = await fetch('/chat/history');
                const data = await response.json();
                this.messages = data.history || [];
                this.displayHistory();
            } catch (error) {
                console.error('Error loading chat history:', error);
            }
        }

        displayHistory() {
            this.messageContainer.innerHTML = '';
            this.messages.forEach(message => {
                this.displayMessage(message.role, message.content);
            });
        }

        displayMessage(role, content) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${role}-message`;
            messageDiv.textContent = content;
            this.messageContainer.appendChild(messageDiv);
            this.messageContainer.scrollTop = this.messageContainer.scrollHeight;
        }

        async sendMessage() {
            console.log('sendMessage called');
            const message = this.userInput.value.trim();
            if (!message) {
                console.log('Empty message, ignoring');
                return;
            }

            // Display user message immediately
            this.displayMessage('user', message);
            this.userInput.value = '';

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message: message })
                });

                const data = await response.json();
                
                // Mostrar SID en consola
                console.log(`Chat Session ID: ${data.session_id}`);
                
                if (data.error) {
                    this.displayMessage('system', `Error: ${data.error}`);
                    return;
                }

                // Display bot response
                this.displayMessage('bot', data.response);
                
                // Update messages array
                this.messages = data.history;

            } catch (error) {
                console.error('Error:', error);
                this.displayMessage('system', 'Error al procesar tu mensaje.');
            }
        }

        async clearHistory() {
            try {
                await fetch('/chat/clear', { method: 'POST' });
                this.messages = [];
                this.messageContainer.innerHTML = '';
            } catch (error) {
                console.error('Error clearing chat history:', error);
            }
        }
    }

    // Modificar la inicialización para crear una instancia global
    let chatManager;

    document.addEventListener('DOMContentLoaded', () => {
        chatManager = new ChatManager();
    });
}); 