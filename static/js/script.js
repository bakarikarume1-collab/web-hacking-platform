
// ===============================
// SMOOTH SCROLLING
// ===============================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener("click", function (e) {
        e.preventDefault();

        const target = document.querySelector(this.getAttribute("href"));

        if (target) {
            target.scrollIntoView({
                behavior: "smooth"
            });
        }
    });
});


// ===============================
// ACTIVE NAV LINK HIGHLIGHT
// ===============================
const links = document.querySelectorAll("nav ul li a");

links.forEach(link => {
    link.addEventListener("click", function () {
        links.forEach(l => l.classList.remove("active"));
        this.classList.add("active");
    });
});


// ===============================
// SCROLL ANIMATION (FADE IN)
// ===============================
const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add("show");
        }
    });
});

document.querySelectorAll(".lesson-card, .hero, .success-zone").forEach(el => {
    el.classList.add("hidden");
    observer.observe(el);
});


// ===============================
// TYPING EFFECT (HERO TEXT)
// ===============================
const heroText = document.querySelector(".hero h1");

if (heroText) {
    const text = heroText.innerText;
    heroText.innerText = "";

    let i = 0;

    function typeEffect() {
        if (i < text.length) {
            heroText.innerHTML += text.charAt(i);
            i++;
            setTimeout(typeEffect, 80);
        }
    }

    typeEffect();
}


// ===============================
// BUTTON HOVER GLOW EFFECT
// ===============================
const buttons = document.querySelectorAll(".btn");

buttons.forEach(btn => {
    btn.addEventListener("mouseenter", () => {
        btn.style.transform = "scale(1.05)";
        btn.style.boxShadow = "0 0 15px cyan";
    });

    btn.addEventListener("mouseleave", () => {
        btn.style.transform = "scale(1)";
        btn.style.boxShadow = "none";
    });
});
