function displayNavbar() {
  var x = document.getElementById("navbar");
  if (x.className === "navbar") {
    x.className += " responsive";
  } else {
    x.className = "navbar";
  }
}

function togglePopup(name) {
  var x = document.getElementById(name);
  if (x) {
    if (x.className === "popup-dim popup-hide") {
      x.className = "popup-dim popup-show";
    } else {
      x.className = "popup-dim popup-hide";
    }
  }
}

function displayTitles(titles) {
  var html = "";
  titles.forEach(function(v) {
    html += `<div class="col-1 col-s-4"> <span>${v[0]}</span> <span>${v[1]}</span> </div>`;
  });
  $(".game-status").html(html);
}
