

const btn_new = document.querySelector(".btn");
const loader = document.querySelector(".loading");
const results = document.querySelector(".results-box");

btn_new.addEventListener("click", function () {

    loader.classList.remove("hidden");
    results.classList.add("hidden")

});
