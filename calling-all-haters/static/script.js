var app = {};
app.events = {};

function formatSeconds(seconds) {
  if (seconds >= 0) {
    const quotient =  (seconds - seconds % 60) / 60;
    const remainder = seconds % 60;
    return `${quotient}:${String(remainder).padStart(2, "0")}`
  } else {
    return "unlimited"
  }
}
function get_key(array, key, value=null) {
  return key in array ? array[key] : value;
}
function displayError(title="Uh oh, something happened!", description="") {
  $("#error-popup-title").text(title);
  $("#error-popup-desc").text(description);
  togglePopup("error-popup", true);
}
function get_cookie(cname) {
  var name = cname + "=";
  var decodedCookie = decodeURIComponent(document.cookie);
  var ca = decodedCookie.split(';');
  for(var i = 0; i <ca.length; i++) {
    var c = ca[i];
    while (c.charAt(0) == ' ') {
      c = c.substring(1);
    }
    if (c.indexOf(name) == 0) {
      return c.substring(name.length, c.length);
    }
  }
  return "";
}
function decode_flask_cookie(val) {
  if (val.indexOf('\\') === -1) {
      return val;  // not encoded
  }
  val = val.slice(1, -1).replace(/\\"/g, '"');
  val = val.replace(/\\(\d{3})/g, function(match, octal) { 
      return String.fromCharCode(parseInt(octal, 8));
  });
  return val.replace(/\\\\/g, '\\');
}
function displayNavbar() {
  var x = document.getElementById("navbar");
  if (x.className === "navbar") {
    x.className += " responsive";
  } else {
    x.className = "navbar";
  }
}
function togglePopup(name, show=false) {
  var x = document.getElementById(name);
  if (x) {
    if (x.className === "popup-dim popup-hide" || show) {
      x.className = "popup-dim popup-show";
    } else {
      x.className = "popup-dim popup-hide";
    }
  }
}
function displayTitles(titles, oneline=false) {
  document.getElementsByClassName("game-status")[0].className = oneline ? 'game-status oneliner' : 'game-status';
  var html = "";
  titles.forEach(function(v) {
    html += `<div class="col-1 col-s-4"> <span>${v[0]}</span> <span>${v[1]}</span> </div>`;
  });
  $(".game-status").html(html);
}
function displayGame(id) {
  $.ajax({
    url: "/api/"
  })
}
function createGame() {
  $.ajax({
    url: "/api/creategame",
    method: "GET",
    success: _resp => {
      if (_resp.success) {
        location.href += "game/" + _resp.data.encoded_id;
      } else {
        displayError(undefined, _resp.error);
      }
    },
    error: _resp => {
      displayError(undefined, "An error occured whilst creating your game");
    }
  })
}
function joinGame(id) {
  if (id in games) {
    if (!(games[id].settings.allow_guests || !get_key(data, "is_guest", true))) {
      displayError("You cannot join this game", "This group is for logged in users only");
      return;
    }
  };
  document.location.href += "game/" + id;
}
function retrieveLeaderboards() {
  const winList = $("#leaderboards-wins");
  const pointsList = $("#leaderboards-points");
  winList.empty().append($("<img>").attr("src", "/static/loader.gif"));
  pointsList.empty().append($("<img>").attr("src", "/static/loader.gif"));
  $.ajax({
    url: "/api/leaderboards",
    method: "GET",
    success: _resp => {
      winList.empty();
      pointsList.empty();
      _resp.wins.forEach(_data => {
        var listing = $("<span>").text(`${_data.name} - ${_data.total_wins} win${_data.total_wins != 1 ? "s" : ""}`)
        if (data.id == _data.id) {
          listing.addClass("leaderboards-self");
          $("#leaderboards-wins-caption").text(`Total Wins: ${_data.total_wins} points (#${_resp.positions.wins+1})`);
        };
        listing.appendTo(winList);
      });
      _resp.points.forEach(_data => {
        var listing = $("<span>").text(`${_data.name} - ${_data.total_points} point${_data.total_points != 1 ? "s" : ""}`)
        if (data.id == _data.id) {
          listing.addClass("leaderboards-self");
          $("#leaderboards-points-caption").text(`Total Points: ${_data.total_points} points (#${_resp.positions.points+1})`);
        };
        listing.appendTo(pointsList);
      });
    },
    error: _ => {
      winList.empty();
      pointsList.empty();
      $("<span>").text("An exception occured whilst retrieving leaderboards :(").appendTo(winList);
      $("<span>").text("An exception occured whilst retrieving leaderboards :(").appendTo(pointsList);
    }
  });
}
function discoverGames(is_guest) {
  const discoveryList = $(".game-discovery");
  discoveryList.empty();
  $("<img>").attr("src", "/static/loader.gif").appendTo(discoveryList);
  $.ajax({
    url: "/api/discovery",
    method: "GET",
    success: _resp => {
      discoveryList.empty();
      if (_resp.length == 0) {
        $("<span>").text("There are no active games currently :(").appendTo(discoveryList);
      }
      _resp.forEach(_data => {
        games[_data.encoded_id] = _data;
        if (_data.has_custom_deck) {
          _data.decks.concat("Custom");
        }
        var joinButton = $("<a>").append(
          $("<button>").html(`Join ${(_data.settings.allow_guests || !is_guest) ? "" : "<img class=\'lock\' src=\'/static/lock-alert.svg\'>"}`)
        )

        joinButton.attr("game-id", _data.encoded_id);
        if (!(_data.settings.allow_guests || !is_guest)) {
          joinButton.attr("data-tooltip", "This group is for logged in users only");
        }
        if (_data.settings.password) {
          joinButton.attr("data-tooltip", "This game has password protection");
        }
        joinButton.on("click", _ => {
          joinGame(_.currentTarget.attributes['game-id'].value)
        })

        display_names = []
        _data.players.forEach(p => {
          display_names = display_names.concat(p.display_name || p.name)
        });
        $("<div>").addClass("game-container").append(
          $("<div>").addClass("game-description").append(
            $("<span>").addClass("title").text(`${_data.host.display_name}'s Game - ${_data.players.length}/${_data.settings.player_limit == null ? "unlimited" : _data.settings.player_limit}`)
          ).append(
            $("<span>").html(`Players: <span>${display_names.join(", ")}</span>`)
          ).append(
            $("<span>").html(`Point Goal: <span>${_data.settings.score_limit}</span>`)
          ).append(
            $("<span>").html(`Decks: <span>${_data.decks}</span>`)
          )
        ).append(
          $("<div>").addClass("game-buttons").append(
            $("<a>").append(
              $("<button>").text("Spectate")
            )
          ).append(
            joinButton
          )
        ).appendTo(discoveryList)
      });
    },
    error: _ => {
      discoveryList.empty();
      $("<span>").text("An exception occured whilst retrieving current games :(").appendTo(discoveryList);
    }});
}
function register() {
  const username = $("#login-username");
  if (username) {
    $.ajax({
      url: "/api/register",
      method: "POST",
      data: {
        "username": username.val(),
        "password": $("#login-password").val()
      },
      success: _resp => {
        if (!_resp.success) {
          return $("#login-error").text(_resp.error);
        }
        document.location.reload();
      }
    })
  }
}
function loginAsGuest(is_index=false) {
  const username = $(is_index == true ? "#play-guest-username" : "#guest-username");
  if (username) {
    $.ajax({
      url: "/api/login",
      method: "POST",
      data: {
        "username": username.val(),
        "guest": "true"
      },
      success: _resp => {
        if (!_resp.success) {
          return $(is_index == true ? "#guest-login-error" : "#login-error").text(_resp.error);
        }
        document.location.reload();
      }
    })
  }
}
function login() {
  const username = $("#login-username");
  if (username) {
    $.ajax({
      url: "/api/login",
      method: "POST",
      data: {
        "username": username.val(),
        "password": $("#login-password").val()
      },
      success: _resp => {
        if (!_resp.success) {
          return $("#login-error").text(_resp.error);
        }
        document.location.reload();
      }
    })
  }
}
function loadDecks() {
  if (app.gamepack_cache == undefined) {
    $.ajax({
      url: "/api/packs/default",
      success: _resp => {
        app.gamepack_cache = {};
        _resp.forEach(d => {
          app.gamepack_cache[d.id] = d
        })
        loadDecks();
      }
    })
  } else {
    var decklist = $(".deck-select");
    decklist.empty();
    Object.values(app.gamepack_cache).forEach(v => {
      $("<label>").append(
        $("<input>").attr("type", "checkbox").attr("deckid", v.id).prop("checked", app._cardpacks.includes(v.id))
      ).append(
        $("<span>").text(v.name)
      ).appendTo(decklist);
    });
  }
}
function addDecks() {
  app._cardpacks = [];
  Object.values($("#game-decks input")).forEach(e => {
    if (e.checked) {
      app._cardpacks = app._cardpacks.concat(e.attributes['deckid'].value);
    }
  });
  renderGamePackList();
}
function renderGamePackList() {
  if (app.gamepack_cache == undefined) {
    $.ajax({
      url: "/api/packs/default",
      success: _resp => {
        app.gamepack_cache = {};
        _resp.forEach(d => {
          app.gamepack_cache[d.id] = d
        })
        renderGamePackList();
      }
    })
  } else {
    var text = [];
    app._cardpacks.forEach(s => {
      if (s in app.gamepack_cache) {
        text = text.concat(app.gamepack_cache[s].name);
      }
    })
    $("#settings-game-packs-preview").val(text.join(", "));
  }
}
function displayBoard() {
  if (app.state == 0) {
    $("#scoreboard").text(`Players (${Object.keys(app.players).length}):`);
    var scoreboard = $(".scoreboard");
    scoreboard.empty();
    Object.values(app.players).forEach(p => {
      var container = $("<div>");
      $("<span>").text(p.display_name).appendTo(container);
      if (p.is_host) {
        $("<img>").addClass("check").addClass("host").attr("src", "/static/crown.svg").appendTo(container);
      }
      container.appendTo(scoreboard);
    });
    if (app.gamepack_cache == undefined) {
      $.ajax({
        url: "/api/packs/default",
        success: _resp => {
          app.gamepack_cache = {};
          _resp.forEach(d => {
            app.gamepack_cache[d.id] = d
          })
          displayBoard();
        }
      })
    } else {
      var white = 0;
      var black = 0;
      var blank = 0;
      var scoreboard = $(".gamepacks");
      var packs = Object.values(app.settings.game_packs);
      scoreboard.empty();
      if (packs.length == 0) {
        $("<span>").text("No packs added").appendTo(scoreboard);
      }
      packs.forEach(p => {
        if (p in app.gamepack_cache) {
          var pack = app.gamepack_cache[p];
          white += pack.white.length;
          black += pack.black.length;
          blank += pack.empty;
          var container = $("<div>");
          $("<span>").addClass("scoreboard-score").text(pack.short).appendTo(container);
          // $("<span>").addClass("scoreboard-score").html("<img src='/static/star.svg'>").appendTo(container);
          $("<span>").text(pack.name).appendTo(container);
          container.appendTo(scoreboard);  
        } else {
          console.warn(`Game pack ${p} is not in cache`);
        }
      })
      $("#gamepack").text(`Game Packs: (${white} white, ${black} black and ${blank} black cards)`);
    }
  } else {
    renderDeck();

    $("#scoreboard").text(`Scoreboard:`);
    var scoreboard = $(".scoreboard");
    scoreboard.empty();
    Object.values(app.players).forEach(p => {
      var container = $("<div>");
      $("<span>").addClass("scoreboard-score").text(p.points).appendTo(container);
      $("<span>").text(p.display_name).appendTo(container);
      if (p.is_host) {
        $("<img>").addClass("check").addClass("selected").attr("src", "/static/crown.svg").appendTo(container);
      }
      container.appendTo(scoreboard);
    })
  }
}
function displayBlackcard(card, picked, convert=false) {
  if (app.gamepack_cache == undefined) {
    $.ajax({
      url: "/api/packs/default",
      success: _resp => {
        app.gamepack_cache = {};
        _resp.forEach(d => {
          app.gamepack_cache[d.id] = d
        })
        displayBlackcard(card, picked);
      }
    })
  } else {
    if (convert) {
      _picked = []
      picked.forEach(id => {
        _picked = _picked.concat(app.deck[id].text);
      })
      picked = _picked;
    }
    var card_content = $("<div>").addClass("card-content");
    var counter = -1;
    var split = card.text.split("_");
    split.forEach(c => {
      card_content.append(c);
      counter += 1;
      if (counter < split.length-1) {
        card_content.append(
          $("<span>").text(picked[counter] || "____________")
        )
      }
    })
    var card_information = $("<div>").addClass("card-information");
    if (card.deck in app.gamepack_cache) {
      card_information.append(
        $("<span>").text(app.gamepack_cache[card.deck].short)
      );
    } else {
      card_information.append(
        $("<span>").text("CSTM")
      );
    }
    cards_selected = card.text.indexOf("_") == -1 ? 1 : (split.length - 1);
    $("<span>").append("Pick ").append(
      $("<b>").text(cards_selected)
    ).append(` card${cards_selected == 1 ? '' : 's'}`).appendTo(card_information);

    var labels = $("#selection-buttons");
    labels.empty();
    $("<h5>").append(
      "Select "
    ).append(
      $("<b>").text(cards_selected)
    ).append(` card${cards_selected == 1 ? '' : 's'} then confirm your selection.`).appendTo(labels);
    $("<button>").on("click", _ => {
      submitSelection(); return false;
    }).addClass("button").text("Confirm Selection").attr("id", "confirmButton").appendTo(labels);
    $(".black-card").empty().append(card_content).append(card_information);
  }
}
function renderDeck() {
  if (app.state == 2 || app.state == 3) {
    if (app.players[data.id].is_czar) {
      var labels = $("#selection-buttons");
      labels.empty().append(
        $("<h5>").text("You are the card czar. Wait until all cards have been played or time runs out then choose who wins the point")
      );
      if (app.state == 3) {
        $("<button>").on("click", _ => {
          submitSelection(); return false;
        }).addClass("button").text("Confirm Selection").attr("id", "confirmButton").appendTo(labels);
      }
    } else {
      if (app.state == 3) {
        var labels = $("#selection-buttons");
        labels.empty().append(
          $("<h5>").text("Waiting for the czar to select a winner...")
        );
      }
    }
    if (app.state == 3) {
      var card_selection = $(".card-selection");
      card_selection.empty();
      $("<h5>").text("Cards Played:").appendTo(card_selection);
      app.others_played.forEach(p => {
        var playerId = p[0];
        var card = p[1];
        if (card != "" && card) {
          var button = $("<button>").addClass("card-stack").attr("player-id", p[0]).bind("click", {id: playerId}, handleSelection)
          var container = $("<div>");
          card.forEach(c => {
            $("<div>").addClass("white-card-stack").append(
              $("<span>").append(c.text)
            ).appendTo(container);
          })
          img = $("<img>").addClass("check").attr("src", "/static/check-alt.svg");
          if (app.played.includes(p[0])) {
            img.addClass("selected")
          }
          button.append(container).append(img).appendTo(card_selection);
          if (p[0] == app.winner_id) {
            button.addClass("won");
          }
        }
      });
      if (app.winner_id in app.players) {
        $("<span>").append(
          $("<b>").text(app.players[app.winner_id].display_name)
        ).append(" scored a point!").appendTo(card_selection);
      }
    } else {
      if (app.players[data.id].is_czar) {
        if (app.state != 3) {
          $(".card-selection").addClass("hidden");
        } else {
          $(".card-selection").removeClass("hidden");
        }
      } else {
        var card_selection = $(".card-selection");
        card_selection.empty();
        $("<h5>").text("Select from your hand:").appendTo(card_selection);
        app.players[data.id].deck.forEach(c => {
          var img = $("<img>").addClass("check").attr("src", "/static/check.svg");
          if (app.played.includes(c.identifier)) {
            img.addClass("selected");
          }
          $("<button>").addClass("white-card").append(
            $("<span>").addClass("card-content").text(c.text)
          ).append(
            img
          ).attr("contents", c.text).attr("card-id", c.identifier).bind("click", {id: c.identifier}, handleSelection).appendTo(card_selection);
        });
        $(".card-selection").removeClass("hidden");
      }
    }
  }
  if (app.submitted.indexOf(data.id) != -1) {
    $(".white-card").attr("disabled", true);
    $("#confirmButton").attr("disabled", true);
  }
}
function handleSelection(clickInformation) {
  if (app.state == 2) {
    var card_id = clickInformation.data.id;
    var max_cards = app.blackcard.text.indexOf("_") == -1 ? 1 : (app.blackcard.text.split("_").length - 1);
    if (app.played.includes(card_id)) {
      app.played.splice( app.played.indexOf(card_id), 1 );
      renderDeck();
      displayBlackcard(app.blackcard, app.played, true);
    } else {
      if (app.played.length < max_cards) {
        app.played = app.played.concat(card_id);
        renderDeck();
        displayBlackcard(app.blackcard, app.played, true);
      }
    }
  }
  if (app.state == 3) {
    var card_id = clickInformation.data.id;
    if (app.players[data.id].is_czar) {
      app.others_played.forEach(p => {
        if (p[0] == card_id) {
          app.played = [card_id];
          cardtext = []
          p[1].forEach(c => {
            cardtext = cardtext.concat(c.text);
          })
          displayBlackcard(app.blackcard, cardtext);
          return;
        }
      })
      renderDeck();
    }
  }
}
function submitSelection() {
  if (app.state == 2) {
    var max_cards = app.blackcard.text.indexOf("_") == -1 ? 1 : (app.blackcard.text.split("_").length - 1);
    if (app.played.length >= max_cards) {
      var cards = app.played.slice(0, max_cards);
      app.ws.send(JSON.stringify({
        "o": 0,
        "e": "PLAYER_SELECT",
        "d": cards
      }))
      $(".white-card").attr("disabled", true);
      $("#confirmButton").attr("disabled", true);
    }
  }
  if (app.state == 3 && app.players[data.id].is_czar && app.played.length == 1) {
    app.ws.send(JSON.stringify({
      "o": 0,
      "e": "CZAR_SELECT",
      "d": app.played[0]
    }))
    $(".white-card").attr("disabled", true);
    $("#confirmButton").attr("disabled", true);
  }
}

function addAppEvent(name, func) {
  if (name in app.events) {
    console.warn(`Event "${name}" has been overwritten`);
  };
  app.events[name] = func;
}

function retrieveNTP() {
  console.debug("Retrieving NTP value");
  var initial = (new Date()).valueOf();
  $.ajax({
    url: "/api/ntp",
    success: _resp => {
      var final = (new Date()).valueOf();
      app.ntp_offset = ((_resp - initial) + (_resp - final)) / 2;
      console.debug(`Retrieved an NTP offset of ${app.ntp_offset}ms`);
    }
  })
}

function displayTitleWithTimer() {
  if (app.state && app.state != 0) {
    var titles = app.common_title;
    if (app.display_timer) {
      var difference = Math.ceil((app.timer_ending - app.timestamp()) / 1000);
      if (difference < 0) {
        difference = 0;
      }
      var formatted = formatSeconds(difference);
      titles = titles.concat([["Time Remaining:", formatted]])
    }
    displayTitles(titles, false);  
  }
}
setInterval(displayTitleWithTimer, 1000);

function connectGame() {
  app.ws_url = (document.location.protocol == "https:" ? "wss:" : "ws:") + "//" + document.location.host + document.location.pathname;

  app.heartbeat_interval = 0;
  app.heartbeat_counter = 0;
  app.heartbeat_task = undefined;
  app.expecting_close = false;
  app.start_time = Date.now();

  app.token = get_cookie("token");
  app.game = undefined;
  app.password = $("#password-input").val() || undefined;

  app.host = undefined;
  app.is_host = false;
  app.players = {};
  app.settings = {};
  app.state = -1;
  app.gamepack_cache = undefined;
  app._cardpacks = [];
  app.winner_id = undefined;
  app.played = [];
  app.round = -1;
  app.ws_failures = 0;
  app.others_played = [];

  app.common_title = [];
  app.display_timer = false;
  app.timer_ending = 0;
  app.submitted = [];

  app.ntp_offset = 0;
  retrieveNTP();
  setInterval(retrieveNTP, 60000);

  app.timestamp = function() {
    return (new Date()).valueOf() + app.ntp_offset;
  }

  app.heartbeat = _ => {
    app.heartbeat_counter += 1;
    console.debug(`Sending heartbeat on counter ${app.heartbeat_counter}`);
    app.ws.send(JSON.stringify({
      "o": 3,
      "d": app.heartbeat_counter
    }))
  }

  app.saveSettings = _ => {
    app.ws.send(JSON.stringify({
      "o": 0,
      "e": "UPDATE_SETTINGS",
      "d": {
        "score_limit": $("#settings-score-limit").val(),
        "timer_limit": $("#settings-timer-limit").val(),
        "allow_guests": $("#settings-allow-guests")[0].checked,
        "player_limit": [$("#settings-player-limit-enabled")[0].checked, $("#settings-player-limit").val()],
        "password": [$("#settings-password-enabled")[0].checked, $("#settings-password").val(), $("#settings-password-show")[0].checked],
        "gamepacks": app._cardpacks,
        "custompacks": $("#settings-custom-game-packs").val()
      }
    }))
  }

  app.startGame = _ => {
    app.ws.send(JSON.stringify({
      "o": 0,
      "e": "GAME_START"
    }))
  }

  app.start_ws = _ => {
    app.ws = new WebSocket(app.ws_url);
    console.debug(`Connecting to ${app.ws_url}`);

    app.close = function() {
      app.expecting_close = true;
      app.ws.close();
    }

    app.ws.addEventListener("open", event => {
      console.debug(`Websocket opened. Sending identify`);
      app.ws_failures = 0;
      app.start_time = Date.now();
      app.ws.send(JSON.stringify({
        "o": 2,
        "d": {
          "t": app.token,
          "p": app.password,
        }
      }));
    });

    app.ws.addEventListener("close", _ => {
      console.debug("Websocket closed.");
      clearInterval(app.heartbeat_task);
      app.ws_failures += 1;
      if (app.ws_failures >= 5) {
        app.expecting_close = true;
        displayError("Failed to reconnect to Websocket :<");
      }
      if (!app.expecting_close) {
        app.start_ws();
      };
    })

    app.ws.addEventListener("message", event => {
      console.debug(`Webscocket message: ${event.data}`);

      try {
        var data = JSON.parse(event.data);
      } catch (e) {
          console.error(`Failed to parse ${event.data}: ${e}`);
          return;
      }

      switch (data.o) {
        case 1:
          app.heartbeat();
          app.heartbeat_interval = data.d * 1000;
          console.debug(`Creating heartbeat task with interval of ${app.heartbeat_interval}`);
          app.heartbeat_task = setInterval(app.heartbeat, app.heartbeat_interval);
          break;
        case 3:
          if (data.t != 2) {
            app.expecting_close = true;
            if (data.t == 1) {
              togglePopup("game-password-popup", true);
              break;
            }
            displayError(undefined, data.m || "An unknown error occured");  
          } else {
            displayError(undefined, data.m || "An unknown error occured");  
          }
          break;
        case 0:
          if (!(data.e in app.events)) {
            console.error(`Unknown event "${data.e}"`);
            break;
          };
          try {
            app.events[data.e](data.d, data);
          } catch (e) {
            console.error(e);
            app.events[data.e](data.d);
          }
      }
    })
  };
  app.start_ws();
}

addAppEvent("PLAYER_UPDATE", d => {
  app.players[d.id] = d;
  if ("deck" in app.players[d.id]) {
    app.deck = {};
    app.players[d.id].deck.forEach(c => {
      app.deck[c.identifier] = c;
    })
  }
  displayBoard();
})

addAppEvent("PLAYER_ADDITION", d => {
  app.players[d.id] = d;
  displayTitles([
    ["Score Limit:", app.settings.score_limit],
    ["Timer Limit:", formatSeconds(app.settings.timer_limit * 60)],
    ["Player Limit:", app.settings.player_limit == null ? "unlimited" : app.settings.player_limit],
    ["Players:", Object.keys(app.players).length]
  ], false);
  displayBoard();
})

addAppEvent("ROUND_END", function(d, m) {
  app.timer_ending = 0;
  app.played = [];
  displayTitleWithTimer();
  if ("winning" in d) {
    app.winner_id = d.winning.id;
    text = [];
    d.winning_card.forEach(c => {
      text = text.concat(c.text);
    })
    displayBlackcard(app.blackcard, text);
  }
  for (player_id in d.scores) {
    if (player_id in app.players) {
      app.players[player_id].points = d.scores[player_id];
    }
  }
  app.events["GAME_UPDATE"](d, m);
})

addAppEvent("ROUND_UPDATE", function(d, m) {
  app.winner_id = 0;
  app.others_played = d.played;
  var state_change = false;
  app.submitted = [];
  d.played.forEach(k => {
    if (typeof(k) == "object") {
      if (k.length > 0) {
        app.submitted.push(k[0])
      }
    }
  })
  if (app.submitted.indexOf(data.id) != -1) {
    $(".white-card").attr("disabled", true);
    $("#confirmButton").attr("disabled", true);
  }
  if (m.s != app.state) {
    console.debug(`State changed from ${app.state} to ${m.s}`);
    app.state = m.s;
    state_change = true;
  }

  if (app.state == 2) {
    app.common_title = [
      ["Round", d.number],
      ["Points", app.players[data.id].points + "/" + app.settings.score_limit],
      ["Remaining", Math.max(1, d.active - d.played.length)]
    ]
    app.blackcard = d.black_card;
    displayBlackcard(app.blackcard, app.played, true);
  }
  if (app.state == 3) {
    app.common_title = [
      ["Round", d.number],
      ["Points", app.players[data.id].points + "/" + app.settings.score_limit]
    ]
    app.blackcard = d.black_card;
    var selection = $(".card-selection");
    selection.removeClass("hidden").empty();
  }
  if (app.state == 4) {
    app.common_title = [
      ["Round", d.number],
      ["Points", app.players[data.id].points + "/" + app.settings.score_limit]
    ]
  }

  if (state_change) {
    if (0 < app.state < 4) {
      app.display_timer = true;
    } else {
      app.display_timer = false;
    }  
    if (app.state == 0) {
      $("#lobby-container").removeClass("hidden");
      $("#board-container").addClass("hidden");
    } else {
      $("#settings-container").addClass("hidden");
      $("#lobby-container").addClass("hidden");
      $("#settings-container-splitter").addClass("hidden");
      $("#board-container").removeClass("hidden");
    }
    // Process state changes
  }
  if ("t" in m) {
    app.timer_ending = m.t;
    displayTitleWithTimer()
  }
  if (d.number != app.round) {
    app.round = d.number;
    app.played = [];
  }
  renderDeck();
  // DISPLAY BLACK CARD
  // START TIMER
})

addAppEvent("GAME_INIT", d => {
  app.state = 0;
  if ("host" in d) {
    app.host = d['host'];
  }
  app.is_host = (app.host.id == data.id);
  if (app.is_host && app.state == 0) {
    $("#settings-container").removeClass("hidden");
    $("#settings-container-splitter").removeClass("hidden");
  } else {
    $("#settings-container").addClass("hidden");
    $("#settings-container-splitter").addClass("hidden");
  }
  d.players.forEach(p => {
    app.players[p.id] = p;
  })
  app.settings = d.settings;
  $("#settings-score-limit").val(app.settings.score_limit);
  $("#settings-timer-limit").val(app.settings.timer_limit);
  if (app.settings.player_limit != null) {
    $("#settings-player-limit").val(app.settings.player_limit);
    $("#settings-player-limit-enabled")[0].checked = true
  }
  if (app.settings.password != null) {
    $("#settings-password").val(app.settings.password);
    $("#settings-password-enabled")[0].checked = true
  }
  $("#settings-password").attr("type", app.settings.show_password == true ? "text" : "password");
  $("#settings-password-show")[0].checked = app.settings.show_password;
  $("#settings-allow-guests")[0].checked = app.settings.allow_guests;
  app._cardpacks = app.settings.game_packs;
  app.events["GAME_UPDATE"](app.settings);
})

addAppEvent("GAME_END", d => {
  $("#selection-buttons").addClass("hidden");
  $(".black-card").addClass("hidden");
  $(".card-selection").addClass("hidden");
  $("#board-container > h5").empty().append(
    $("<b>").text(d.display_name)
  ).append(" has won the game!")
})

addAppEvent("GAME_UPDATE", d => {
  if (0 < app.state < 4) {
    app.display_timer = true;
  } else {
    app.display_timer = false;
  }
  if (app.state == 0) {
    app.settings = d;
    renderGamePackList();
    displayTitles([
      ["Score Limit:", app.settings.score_limit],
      ["Timer Limit:", formatSeconds(app.settings.timer_limit * 60)],
      ["Player Limit:", app.settings.player_limit == null ? "unlimited" : app.settings.player_limit],
      ["Players:", Object.keys(app.players).length]
    ], false);
	$("#settings-password").attr("type", app.settings.show_password == true ? "text" : "password");
    if (app.settings.show_password && app.settings.password) {
      $("#game-password b").html(app.settings.password);
      $("#game-password").removeClass("hidden")
    } else {
      $("#game-password").addClass("hidden")
    };
    $("#lobby-container").removeClass("hidden");
    $("#board-container").addClass("hidden");
  } else {
    $("#lobby-container").addClass("hidden");
    $("#board-container").removeClass("hidden");
  }
  displayBoard();
})

$(_ => {
  const cookie = decode_flask_cookie(get_cookie("data"));
  if (cookie) {
    data = JSON.parse(cookie);
  } else {
    data = {}
  }
  games = {};
  $(".index-items a").toArray().forEach(_obj => {
    if (_obj.href) {
      var url = new URL(_obj.href);
      if (url.pathname == document.location.pathname) {
        _obj.setAttribute("id", "current-link")
      }  
    }
  })
})