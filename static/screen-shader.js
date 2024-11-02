// static/screen-shader.js
const afterBodyReadyScreenshader = (() => {
    // Screen shader functionality
    const setShade = (level) => {
        document.documentElement.style.setProperty('--shade-level', level);
        localStorage.setItem('shade-level', level);
    };

    // Check stored preference
    const storedShade = localStorage.getItem('shade-level');
    if (storedShade) {
        setShade(storedShade);
    }
})();