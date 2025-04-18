# Online Cinema

## General Description
An online cinema is a digital platform that allows users to select, watch, 
and purchase access to movies and other video materials via the internet. 
These services have become popular due to their convenience, a wide selection of content, 
and the ability to personalize the user experience.

## Key Features of Online Cinema

### Authorization and Authentication
#### User Registration:
* Users should be able to register using their email. After registration, an email is sent with a link to activate their account. If the user does not activate their account within 24 hours, the link becomes invalid.
* If the user fails to activate their account within 24 hours, user has the option to enter email to receive a new activation link, valid for another 24 hours.
* Task celery-beat is using to periodically delete expired activation tokens.
* User email should be unique for registration.
#### Login and Logout:
* After logging out of the Online Cinema, the user's JWT token is deleted, making it unusable for further logins.
#### Password Management:
* Users can change their password if they remember the old one by entering the old password and a new password.
* Users who forget their password can enter their email. If the email is registered and active, a reset link is sent, allowing them to set a new password without confirming the old one.
* Password complexity must pass a validation.
#### JWT Token Management:
* Users receive a pair of JWT tokens (access and refresh) upon login.
* Users can use the refresh token to obtain a new access token with a shorter time-to-live (TTL).
#### User Groups:
* **User**: Access to the basic user interface.
* **Moderator**: In addition to catalog and user interface access, can manage movies on the site through the admin panel, view sales, etc.
* **Admin**: Inherits all permissions from the above roles and can manage users, change group memberships, and manually activate accounts.
#### DB schema:
[Accounts DB schema](https://dbdiagram.io/d/Accounts-app-675ef6bee763df1f00fd8ed1)

### Movies
#### User Functionality:
* Browse the movie catalog with pagination.
* View detailed descriptions of movies.
* Like or dislike movies.
* Write comments on movies.
* Filter movies by various criteria (e.g., name contains.., release year, IMDb rating from..).
* Sort movies by different attributes (e.g., (name, year, price, imdb, id).
* Search for movies by title, genres, stars, or directors.
* Add movies to favorites list.
* Remove movies from favorites.
* View a list of genres with the count of movies in each.
* Rate movies on a 10-point scale.
* Users receive an email notification when their comments receive replies or likes.
#### Moderator Functionality:
* Perform CRUD operations on movies.
* Prevent the deletion of a movie if at least one user has purchased it.
#### DB schema
[Movies DB schema](https://dbdiagram.io/d/Movies-app-675f03b9e763df1f00fe4769)

### Shopping Cart
#### User Functionality:
* Users can add movies to the cart if they have not been purchased yet.
* If the movie has already been purchased, a notification is displayed, indicating that repeat purchases are not allowed.
* Users can remove movies from the cart if they decide not to proceed with the purchase.
* Users can view a list of movies in their cart.
* For each movie in the cart, the title, price, genre, and release year are displayed.
* Users can pay for all movies in the cart at once.
* After successful payment, movies are moved to the "Purchased" list.
* Users can manually clear the cart entirely.
* Will be excluded movies already purchased, notifying the user.
* Will be prevented adding the same movie to the cart more than once.
#### Moderator Functionality:
* Admins can view the contents of users' carts for analysis or troubleshooting.
* Moderators will be notified when attempting to delete a movie that exists in users' carts.
#### Shopping cart DB schema
[Carts DB schema](https://dbdiagram.io/d/Cart-app-675f0d88e763df1f00fed027)

### Orders
#### User Functionality:
* Users can place orders for movies in their cart.
* Users can view a list of all their orders.
* For each order, the following details are displayed:
  * Date and time.
  * List of movies included.
  * Total amount.
  * Order status (paid, canceled, pending).
* After confirming an order, users are redirected to a payment gateway.
* Users can cancel orders before payment is completed.
* After successful payment, users receive an email confirmation.
* **Validation:**
  * Users need ensure the cart is not empty before placing an order.
  * The movies already purchased by the user excluded from order with notice to users.
  * The movies already that in other orders (pending or paid) excluded from order with notice to users.
  * The total order amount will be changed taking into account the actual price of the goods (if the price changes at the time of payment).
* Users can track their order history, including the movies purchased, the final amount paid, and the current status of each order.
* The financial records remain consistent over time, essential for audits, refunds, and reporting.
* The status field in Order allows for workflow management, including pending payment, cancellation, and handling refunds.
#### Moderator Functionality:
* Admins can view all user orders with filters for:
  * Users.
  * Dates.
  * Statuses (paid, canceled, etc.).
#### DB schema
[Orders DB schema](https://dbdiagram.io/d/Order-app-675f141ce763df1f00ff29cb)

### Payments
#### User Functionality:
* Users can make payments using Stripe.
* After payment, users receive a confirmation on the website and via email.
* Users can view the history of all their payments, including:
  * Date and time.
  * Amount.
  * Status (successful, canceled, refunded).
* **Validation**:
  * Verify the total amount of the order.
  * User can pay if user is authenticated.
  * Validate transactions through webhooks provided by the payment system.
  * Update the order status upon successful payment.
  * If a transaction is declined, display recommendations to the user (e.g., "Try a different payment method").
#### Moderator Functionality:
* Admins can view a list of all payments with filters for:
  * Users.
  * Dates.
  * Statuses (successful, refunded, canceled).
* **Functional Implications**:
  * Users have a clear history of all their payments, including details of when, how much, and which items were paid for.
  * The status field and external_payment_id facilitate robust integration with external payment gateways (like Stripe), enabling features like refunds, cancellations, and transaction validations through webhooks.
  * Detailed payment itemization (PaymentItem) supports precise financial audits, reporting, and troubleshooting in case of disputes or inquiries.
#### DB schema
[Payments DB schema](https://dbdiagram.io/d/Payment-app-675f1a65e763df1f00ff70c6)

## How to run Online Cinema:


### Single Command Setup:
  `docker-compose up --build`


### Manual startup:
*   **Should be installed**:
  * `pip install Pillow`
  * `pip install python-multipart`
  * `docker pull minio/mc`
  * `pip install celery celery-sqlalchemy-scheduler kombu`
  * `pip install Redis`
  * `pip install celery[redis]`
  * `pip install fastapi_filter`
  * `pip install stripe==6.6.0`
  * `docker pull stripe/stripe-cli`
  * for testing:
    * `pip install pytest`
    * `pip install httpx`
    * `pip install beautifulsoup4`


* Project path `export PYTHONPATH=src`
* Server Online Cinema (port: 8000) `uvicorn src.main:app --reload`
  * Uvicorn running on http://127.0.0.1:8000 
* Server MailHog in Docker  `docker run --name mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog`
  * Serving under http://127.0.0.1:8025/
* Server MinIO in Docker  `docker run -d -p 9000:9000 --name minio-container -e MINIO_ACCESS_KEY=minioadmin -e MINIO_SECRET_KEY=minioadmin minio/minio server /data`
  * Checking MinIO `docker logs minio-container`
* Run container MinIO Client  `docker run --rm -it minio/mc`
* Interactive session of MinIO  `docker exec -it minio-container sh`
  * sh-5.1# `mc alias set minio http://127.0.0.1:9000 minioadmin minioadmin`   # mc alias
  * sh-5.1# `mc mb minio/cinema-storage`   # mc create bucked
  * check how to work (optional):
    * sh-5.1# `echo "This is a test file" > testfile.txt`
    * sh-5.1# `mc cp testfile.txt minio/cinema-storage`
    * sh-5.1# `mc ls minio/cinema-storage/avatars`  # after create new user profile ([2025-03-08 19:07:31 UTC]  54KiB STANDARD 1_photo.jpg)
    * sh-5.1# `mc rm minio/cinema-storage/avatars/1_photo.jpg`  # clean, if it needs
* Run Redis docker  `docker run -d --name redis -p 6379:6379 redis`
* Run Celery worker   `celery -A src.config.celery_app worker --loglevel=info --pool=solo`   #  check thar registered task:  [tasks] . delete_expired_activation_tokens
* Run Celery beat  for task scheduler  `celery -A src.config.celery_app beat --loglevel=info`  # run celery task one time for 12 hours
* Server for webhook (port: 4242)  `uvicorn src.main:app --reload --host 0.0.0.0 --port 4242`
  * Uvicorn running on http://127.0.0.1:4242   # for get webhooks
* Run Stripe CLI  `docker run -it --rm -e STRIPE_API_KEY=<your stripe secret key> stripe/stripe-cli listen --forward-to http://host.docker.internal:4242/api/v1/payments/webhook/`
**Testing**
* Run tests  `pytest src/tests/`


### Show how it is working:
* Create some movies to DB:  `python -m src.config.movies_to_db`
