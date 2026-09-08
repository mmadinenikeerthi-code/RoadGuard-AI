// ==========================================================
// ROADGUARD AI
// FRONTEND API CONFIGURATION
// ==========================================================


// Backend URL

const API_BASE_URL = "http://127.0.0.1:8000";


// ==========================================================
// FETCH HOTSPOTS
// ==========================================================

async function fetchHotspots() {


    // ------------------------------------------------------
    // GET HTML ELEMENTS
    // ------------------------------------------------------

    const output =
        document.getElementById("output");


    const status =
        document.getElementById("status");


    const button =
        document.getElementById("fetchButton");


    // ------------------------------------------------------
    // LOADING STATE
    // ------------------------------------------------------

    status.textContent =
        "⏳ Fetching hotspot data...";


    output.textContent =
        "Loading data from backend...";


    button.disabled = true;


    try {


        // --------------------------------------------------
        // API REQUEST
        // --------------------------------------------------

        const response = await fetch(

            `${API_BASE_URL}/hotspots/`

        );


        // --------------------------------------------------
        // READ RESPONSE
        // --------------------------------------------------

        const data =
            await response.json();


        // --------------------------------------------------
        // HANDLE API ERROR
        // --------------------------------------------------

        if (!response.ok) {


            status.textContent =
                `❌ API Error: ${response.status}`;


            output.textContent =
                JSON.stringify(
                    data,
                    null,
                    2
                );


            return;

        }


        // --------------------------------------------------
        // SUCCESS
        // --------------------------------------------------

        status.textContent =
            "✅ Hotspot data loaded successfully!";


        output.textContent =
            JSON.stringify(
                data,
                null,
                2
            );


        console.log(
            "Hotspots API Response:",
            data
        );


    }


    catch (error) {


        // --------------------------------------------------
        // CONNECTION ERROR
        // --------------------------------------------------

        console.error(
            "Backend connection error:",
            error
        );


        status.textContent =
            "❌ Cannot connect to backend";


        output.textContent =

`Error connecting to backend:

${error.message}

Make sure:

1. FastAPI backend is running
2. Backend URL is correct
3. Backend is running on port 8000

Backend URL:

${API_BASE_URL}`;


    }


    finally {


        // --------------------------------------------------
        // ENABLE BUTTON AGAIN
        // --------------------------------------------------

        button.disabled = false;


    }


}