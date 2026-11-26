(() => {
    const cards = document.querySelectorAll("[data-vehicle-card]");
    const name = document.querySelector("[data-preview-name]");
    const mileage = document.querySelector("[data-preview-mileage]");
    const link = document.querySelector("[data-preview-link]");

    if (!name || !mileage || !link) return;

    cards.forEach((card) => {
        card.addEventListener("click", () => {
            cards.forEach((item) => {
                const selected = item === card;
                item.classList.toggle("selected", selected);
                item.setAttribute("aria-pressed", String(selected));
            });

            name.textContent = card.dataset.name;
            mileage.textContent = `${Number(card.dataset.mileage).toLocaleString()} km`;
            link.href = card.dataset.url;
        });
    });
})();
