/**
 * Voice input module for the Todo CLI PWA.
 * Uses the Web Speech API for browser-native speech recognition.
 */
const Voice = (() => {
    let recognition = null;
    let isListening = false;

    function isSupported() {
        return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
    }

    function init() {
        if (!isSupported()) return null;

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        return recognition;
    }

    function startListening(onResult, onError, onEnd) {
        if (!recognition) init();
        if (!recognition) {
            if (onError) onError('Speech recognition not supported');
            return;
        }

        recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0].transcript)
                .join('');
            const isFinal = event.results[event.results.length - 1].isFinal;
            if (onResult) onResult(transcript, isFinal);
        };

        recognition.onerror = (event) => {
            isListening = false;
            if (onError) onError(event.error);
        };

        recognition.onend = () => {
            isListening = false;
            if (onEnd) onEnd();
        };

        isListening = true;
        recognition.start();
    }

    function stopListening() {
        if (recognition && isListening) {
            recognition.stop();
            isListening = false;
        }
    }

    function getIsListening() {
        return isListening;
    }

    return {
        isSupported,
        init,
        startListening,
        stopListening,
        isListening: getIsListening
    };
})();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Voice;
}
