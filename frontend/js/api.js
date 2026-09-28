const API_BASE_URL = "";

const API = {
    async get(endpoint) {
        try {
            const res = await fetch(`${API_BASE_URL}${endpoint}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
            return await res.json();
        } catch (err) {
            console.error(`GET ${endpoint} failed:`, err);
            throw err;
        }
    },

    async postForm(endpoint, formData) {
        try {
            const res = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: "POST",
                body: formData
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
            return await res.json();
        } catch (err) {
            console.error(`POST ${endpoint} failed:`, err);
            throw err;
        }
    },

    async post(endpoint) {
        try {
            const res = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: "POST"
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
            return await res.json();
        } catch (err) {
            console.error(`POST ${endpoint} failed:`, err);
            throw err;
        }
    },

    async delete(endpoint) {
        try {
            const res = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: "DELETE"
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
            return true;
        } catch (err) {
            console.error(`DELETE ${endpoint} failed:`, err);
            throw err;
        }
    }
};