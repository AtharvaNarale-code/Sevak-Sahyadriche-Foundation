document.addEventListener("DOMContentLoaded", function () {

    const menuButton =
        document.getElementById("menuButton");

    const menuClose =
        document.getElementById("menuClose");

    const sideMenu =
        document.getElementById("sideMenu");

    const menuOverlay =
        document.getElementById("menuOverlay");


    function openMenu() {

        sideMenu.classList.add("open");

        menuOverlay.classList.add("show");

        document.body.style.overflow =
            "hidden";

    }


    function closeMenu() {

        sideMenu.classList.remove("open");

        menuOverlay.classList.remove("show");

        document.body.style.overflow =
            "";

    }


    if (menuButton) {

        menuButton.addEventListener(
            "click",
            openMenu
        );

    }


    if (menuClose) {

        menuClose.addEventListener(
            "click",
            closeMenu
        );

    }


    if (menuOverlay) {

        menuOverlay.addEventListener(
            "click",
            closeMenu
        );

    }


    document.querySelectorAll(
        ".side-menu a"
    ).forEach(function (link) {

        link.addEventListener(
            "click",
            closeMenu
        );

    });


    document.addEventListener(
        "keydown",
        function (event) {

            if (event.key === "Escape") {

                closeMenu();

            }

        }
    );

});