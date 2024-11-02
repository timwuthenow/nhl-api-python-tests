// static/night-mode.js
const afterBodyReady = (() => {
    // Night mode functionality
    const toggleNightMode = () => {
        document.body.classList.toggle('night-mode');
        localStorage.setItem('night-mode', document.body.classList.contains('night-mode'));
    };

    // Check stored preference
    if (localStorage.getItem('night-mode') === 'true') {
        document.body.classList.add('night-mode');
    }
})();