export async function renderHome(app) {
  app.innerHTML = `
    <div class="container">
      <div class="hero">
        <h1><span>Welcome</span></h1>
        <p>This instance is ready. Open the lab to start working, or configure the frontend from settings.</p>
      </div>
    </div>
  `;
}
