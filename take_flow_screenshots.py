import asyncio
import os
import time

from playwright.async_api import async_playwright


async def take_screenshots() -> None:
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        # Define output directory
        project_root = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(project_root, "screenshots")
        os.makedirs(output_dir, exist_ok=True)

        try:
            # 0. API Documentation
            print("Navigating to API documentation page...")
            await page.goto("http://127.0.0.1:8000/web/API.html")
            await page.wait_for_timeout(2000)  # Wait for page load
            print("Taking screenshot of API Documentation...")
            # Take a full page screenshot of the documentation
            await page.screenshot(
                path=os.path.join(output_dir, "00_api_documentation_full.png"), full_page=True
            )
            # Take a viewport screenshot of the overview
            await page.screenshot(
                path=os.path.join(output_dir, "00_api_documentation_overview.png")
            )

            print("Navigating to registration page...")
            await page.goto("http://127.0.0.1:8000/web/register.html")
            await page.wait_for_timeout(2000)  # Wait for animations

            # 1. Registration Form
            print("Taking screenshot of registration form...")
            await page.screenshot(path=os.path.join(output_dir, "01_registration_form.png"))

            # Fill the form
            unique_id = int(time.time())
            username = f"flow_user_{unique_id}"
            email = f"flow_{unique_id}@example.com"
            password = "TestPassword123!"

            print(f"Filling form with username: {username}, email: {email}")
            await page.fill("#username", username)
            await page.fill("#email", email)
            await page.fill("#password", password)
            await page.fill("#confirm-password", password)
            await page.screenshot(path=os.path.join(output_dir, "02_registration_filled.png"))

            # 2. Registration Processing
            print("Submitting and taking screenshot...")
            # Click with wait for navigation or state change
            await page.click("button[type='submit']")

            # Wait for transition to processing
            try:
                await page.wait_for_selector("#step-processing.active", timeout=10000)
                await page.screenshot(
                    path=os.path.join(output_dir, "03_registration_processing.png")
                )
            except Exception:
                # Take debug screenshot if we get stuck or error element shows
                await page.screenshot(path=os.path.join(output_dir, "debug_error_on_submit.png"))
                # Check for explicit error messages
                error_msg = await page.inner_text("#password-error")
                print(f"Submission might have failed. Error element text: {error_msg}")
                raise

            # 3. Registration Success
            print("Waiting for success and taking screenshot...")
            await page.wait_for_selector("#step-success.active", timeout=15000)
            await page.wait_for_timeout(1000)  # Wait for success animation
            await page.screenshot(path=os.path.join(output_dir, "04_registration_success.png"))

            # 4. Checkout Cart
            print("Proceeding to checkout...")
            await page.click("a:has-text('Proceed to Dashboard')")
            # The destination is checkout.html on the same file server
            await page.wait_for_url("**/checkout.html", timeout=10000)
            await page.wait_for_selector("#step-cart.active", timeout=15000)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=os.path.join(output_dir, "05_checkout_cart.png"))

            # 5. Checkout Payment Details
            print("Proceeding to payment details...")
            await page.click("#btn-proceed")
            await page.wait_for_selector("#step-payment.active", timeout=15000)
            await page.wait_for_timeout(4000)  # Let Stripe elements load
            await page.screenshot(path=os.path.join(output_dir, "06_checkout_payment_details.png"))

            print(f"Screenshots saved to {output_dir}")
        except Exception as e:
            await page.screenshot(path=os.path.join(output_dir, "error_final_state.png"))
            print(f"An error occurred: {e}")
            # Log HTML for debugging
            html = await page.content()
            with open(os.path.join(output_dir, "flow_error_debug.html"), "w") as f:
                f.write(html)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(take_screenshots())
