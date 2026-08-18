const sidebar = document.getElementById("sidebar");
const backgroundImage = document.getElementById("backgroundImage");
const mainTitle = document.getElementById("mainTitle");
const mainDescription = document.getElementById("mainDescription");
const categoryFilter = document.getElementById("categoryFilter");
const searchInput = document.getElementById("searchInput");

let page = 1;
const limit = 10;
let category = "";
let search = "";

function setMainContent(imageSrc, title, description) {
  //Function btst2bl image w title w description
  backgroundImage.style.opacity = "0"; //5ly el sora t5tfe (opacity = 0) 3shan n3ml animation
  backgroundImage.style.backgroundImage = "none"; //Ems7 el sora el adema
  backgroundImage.style.backgroundImage = `url("/static/${imageSrc}")`; //7ot el sora el gdeda mn folder static

  mainTitle.textContent = title;
  mainDescription.textContent = description;

  requestAnimationFrame(() => {
    // when im cilcking on another pic
    backgroundImage.style.opacity = "2";
  });
}

function loadProducts() {
  //Function btgeb kol el products mn API
  fetch(
    //Btb3t request ll server 3shan tgeb el data
    `/api/products?page=${page}&limit=${limit}&category=${category}&search=${search}`, //Bt3ml request ll API w tb3t m3ah page + limit + category + search
  )
    .then((response) => response.json()) //lma taklm server ro7 5od data mn server
    .then((images) => {
      document
        .querySelectorAll(".sidebarItem") //Returns all element descendants of node that match selectors.
        .forEach((item) => item.remove());

      images.forEach((image) => {
        const card = document.createElement("div"); //he createElement() method of the Document interface creates a new HTMLElement that has the specified localName.
        card.className = "sidebarItem";

        const img = document.createElement("img");
        img.src = "/static/" + image.src;
        img.alt = image.title;

        img.onclick = function () {
          setMainContent(image.src, image.title, image.description);
        };

        const title = document.createElement("div");
        title.className = "thumbTitle";
        title.textContent = image.title;

        card.appendChild(img);
        card.appendChild(title);

        sidebar.appendChild(card);
      });

      if (images.length > 0) {
        setMainContent(images[0].src, images[0].title, images[0].description); //hena ba2lo mn img 0 fema akbr a3rf m3ha kolo ba eki a7ddo
      }
    })
    .catch((error) => {
      console.error(error);
    });
}

categoryFilter.addEventListener("change", function () {
  category = this.value;
  page = 1;
  loadProducts();
});
searchInput.addEventListener("input", function () {
  search = this.value;
  page = 1;
  loadProducts();
});

loadProducts();

const form = document.querySelector("form");

if (form) {
  const username = document.querySelector('input[name="username"]');
  const email = document.querySelector('input[name="email"]');
  const password = document.querySelector('input[name="password"]');

  form.addEventListener("submit", function (e) {
    // Remove extra spaces
    if (username) username.value = username.value.trim();
    if (email) email.value = email.value.trim();

    // Username Validation
    if (username && username.value === "") {
      e.preventDefault();
      alert("Please enter your username.");
      username.focus();
      return;
    }

    // Email Validation (Register only)
    if (email) {
      const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

      if (!emailPattern.test(email.value)) {
        e.preventDefault();
        alert("Please enter a valid email.");
        email.focus();
        return;
      }
    }

    // Password Validation
    if (password && password.value.length < 8) {
      e.preventDefault();
      alert("Password must be at least 8 characters.");
      password.focus();
      return;
    }
  });
}
