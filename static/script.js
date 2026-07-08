const sidebar = document.getElementById("sidebar");
const backgroundImage = document.getElementById("backgroundImage");
const mainTitle = document.getElementById("mainTitle");
const mainDescription = document.getElementById("mainDescription");

function setMainContent(imageSrc, title, description) {
  backgroundImage.style.opacity = "0";
  backgroundImage.style.backgroundImage = "none";
  backgroundImage.style.backgroundImage = `url("/static/${imageSrc}")`;
  mainTitle.textContent = title;
  mainDescription.textContent = description;
  requestAnimationFrame(() => {
    backgroundImage.style.opacity = "1";
  });
}
fetch("/api/products")
  .then((response) => response.json())
  .then((images) => {
    images.forEach(function (image) {
      const card = document.createElement("div");
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
      setMainContent(images[0].src, images[0].title, images[0].description);
    }
  })
  .catch((error) => {
    console.error("Error loading products:", error);
  });
