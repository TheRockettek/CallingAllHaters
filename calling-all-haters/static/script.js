function displayNavbar() {
  var x = document.getElementById("navbar");
  if (x.className === "navbar") {
    x.className += " responsive";
  } else {
    x.className = "navbar";
  }
}

function displayTitles(titles) {
  var html = "";
  titles.forEach(function(v) {
    html += `<div class="col-1 col-s-4"> <span>${v[0]}</span> <span>${v[1]}</span> </div>`;
  });
  $(".game-status").html(html);
}
