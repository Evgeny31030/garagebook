(() => {
    const buttons = document.querySelectorAll("[data-theme-choice]");

    function setTheme(theme) {
        document.documentElement.dataset.theme = theme;
        buttons.forEach((button) => {
            button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme));
        });
        try {
            localStorage.setItem("garagebook-theme", theme);
        } catch (error) {
            // Theme still works when browser storage is unavailable.
        }
    }

    const initialTheme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
    setTheme(initialTheme);
    buttons.forEach((button) => {
        button.addEventListener("click", () => setTheme(button.dataset.themeChoice));
    });
})();
