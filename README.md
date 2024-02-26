# Board Game Library
### Video Demo:  <URL https://youtu.be/gDveeUHhvas>
### Description: A website to track and rate the board games you and your friends own.

My friends and I really enjoy playing board games together and we all have large collections. It is hard to remember what games we all own! I wanted a way to easily track and rate what board games we own. I decided to make a website where we could each have our own "virtual board game shelf" and combine them into a "virtual board game library".

Many board gamers are familiar with a very useful website called [Board Game Geek](https://boardgamegeek.com/), aka BGG. For my project I use the BGG API (specifically the BGG XML API2) to request data from BGG, which comes back in XML format. Information about their API can be found [here](https://boardgamegeek.com/wiki/page/BGG_XML_API2).

The back-end of this project is written in Python and uses Flask and an SQLite database. The front-end uses HTML, CSS, JavaScript, Bootstrap, and Jinja.

## Development Process

### Implement Basic User Functionality (sign up, log in, log out)
The first features I implemented were allowing users to create an account, log in, and log out. This was pretty straight-forward and similar to the CS50 Week 9 "Finance" assignment. I created a ***users*** table in the database where I could store a unique ID ***(users.id)*** along with their username ***(users.username)*** and a hashed password ***(users.hash)***.

### Implement Functionality to Add Games to Shelf (search for game, add to shelf)
Next I had to come up with a way to let users add board games to their shelves. I considered just allowing users to type in a board game name, but I wanted games on different user shelves to have the same underlying ID. I also didn't want a situation where two friends appeared to own different games, but they had just spelled them slightly differently. Using the BGG API was a way to resolve this problem. I had trouble even knowing where to begin, but eventually managed to make use of the API within my website as follows:
- the user types all or part of a board game title into a search field then clicks "Look Up Game"
- an API request is sent to BGG for that title, and it returns in XML format a list of games matching or containing the searched title, along with the Board Game Geek's unique ID (and some other information that I don't use)
- the IDs and titles from the XML are converted to a Python dictionary and all of the titles are displayed clearly to the user
- the user selects the radio button with the correct title to add to their shelf
    - many searches return multiple results (e.g., various expansions or even the game in other languages), and there are multiple games with the same title. I made each title also work as a link to the actual BGG page for that game so that users could confirm which was the correct one to select.

I created three new tables to handle this feature.
- The ***games*** table was very simple, with a unique ID field ***(games.id)***, which matches the unique ID used on BGG, and a title field ***(games.title)***. Any game added to a user's shelf gets added to the ***games*** table (if not already present).
- The ***shelves*** table has user ID ***(shelves.user_id)*** and game ID ***(shelves.game_id)*** fields that reference ***users.id*** and ***games.id*** and together serve as a unique identifier within ***shelves***. There is also an "owned" field ***(shelves.owned)*** and a "rating" field ***(shelves.rating)*** within this table that I'll describe later.
- Finally, I made a ***temp_api_queries*** table to temporarily store the results of a user's most recent API results. This kept track of the user's id, the game's id, and the game's title. When a user does a new search, selects a game to add, or signs in, their existing entries are purged from the table to save space. The reason for this table was to be able to do back-end validation to make sure a user didn't edit the HTML to add any ID or even add a game with a modified title to the database. Initially I had the search and the search results on separate pages and I was having trouble keeping the data available, so (with guidance from the "CS50 Duck Debugger") I made this table to keep track of the information temporarily. Later I ended up combining the content onto the same page so it is possible there was a different solution I could have used.

#### Implement User Shelf Functionality (view shelf, delete games, rate games, sort by title or rating)

Next I created a page where a user could actually view the games on their shelf. This involved querying the ***shelves*** and ***games*** tables, then putting the game titles into an HTML table for the user to view. I also added the ability to remove a game from their shelf, and the abilty to rate a game from 10 (best) to 1 (worst). By default the rating was 0 (displayed as "--") meaning 'not rated'. I also implemented the ability to sort by title (A-Z) or rating (highest to lowest). Adding the ability for the user to change a rating for a game wasn't too hard, but I didn't like that my implementation would reload the page, which felt unnecessary and would reset the sorting. With guidance from the "CS50 Duck Debugger" to use an AJAX solution I sent a JSON string with an xhttp request that updated the database without reloading the page.

*Side note*: I originally had a ***shelves*** table that just contained unique pairs of user IDs and game IDs. Their presence in the table indicated that the user owned that game. I also originally had a separate ***ratings*** table where I had the unique pairs of user IDs and game IDs again, plus a rating (from 0 to 10). This worked well for a while as it was easy to allow a user to have a rating for a game that they do not own (such as a friend's game, or a game they previously owned), and the concepts of ownership and ratings felt like they deserved different tables. However, I didn't like that the user ID and game ID pairs ended up in both tables frequently, and more complex queries I worked on later with friend's shelves and the whole library ended up being problematic. I finally changed it so that it was all in one ***shelves*** table, and ownership was defined with an "owned" field (1 for owned, 0 for not owned).

#### Implement Friendship Functionality (send or cancel friend requests, accept or decline friend requests, remove friends)

The next task was to implement a "friendship" feature, which involved letting users send friend requests, cancel sent friend requests, accept or decline friend requests, and delete friends. I created a ***friends*** table that had a unique pair of user IDs (***friends.user_id_1*** and ***friends.user_id_2*** which reference the ***users*** table) and a status ***(friends.status)*** with "1" for friends or "0" for a pending friend request. I had trouble deciding if I should have just one entry for each friendship pair or have two reciprocal entries. I ended up finding it simpler for later queries to just have two reciprocal entries for each friendship, so I just made sure I added/updated/deleted both entries at the same time.

### Implement Functionality to View Shelves of Friends (view friend shelf, rate games, sort games)

Once I had friendships implemented I added the ability to view friends' shelves (their games and ratings). I was able to use the rating functionality from earlier so users could also rate friends' games that they didn't necessarily own. Users can click on the table headers to sort by title, the friend's rating, or their own rating.

### Update Website Appearance (make more use of Bootstrap)

I think it was around this time I decided that the website looked too 'boring' and similar to the CS50 Week 9 "Finance" assignment, so I started playing more with HTML, CSS, and Bootstrap to make it look at least a little more modern. I tried to make sure the website had a responsive design so it looks okay on different screen sizes and I think I mostly achieved it, though there are some cases where the word wrapping doesn't line up as well as I'd like.

### Library Functionality (view all games on shelf and friends' shelves)

Finally I put everything together and created the library feature. This ended up being much more complicated than I had thought, and this was when I started restructuring some of my database tables. I had to change my original idea a bit too, but I'm still pretty happy with the result. My original idea was to able to see each of my friend's ratings for each game in the library (and maybe an average), but I didn't have a clean way to display this (especially once there were more than a couple friends). Also, the queries got so complex that I had to do a less ideal query then manipulate the data afterward in Python, but then lost the ability to sort by title vs rating. I also wanted to choose to view custom libraries or with subsets of friends for different gaming sessions, but ran into similar problems. If I were to continue this project, those are areas I would want to focus on. It would also be nice to keep track of (and therefore sort) the player count for each game, the time estimate, and maybe even plays. There is a lot that could be done to enhance the website, but I am very happy that I was able to reach my initial goal.


