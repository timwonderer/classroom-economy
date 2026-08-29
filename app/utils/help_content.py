"""
Help and support documentation content for Classroom Token Hub.
Structured for Teacher (General Adult) and Student (Middle School) audiences.
"""

HELP_ARTICLES = {
    "teacher": {
        "how_to": [
            {
                "id": "getting_started",
                "title": "Start Here",
                "content": """
                    <p>Use these first steps to get your classroom ready:</p>
                    <ol>
                        <li><strong>Finish setup:</strong> Open your classroom dashboard and turn on the features you want to use.</li>
                        <li><strong>Check your class scope:</strong> Make sure you are working in the correct class before making changes.</li>
                        <li><strong>Add students:</strong> Go to <strong>Students</strong>. You can:
                            <ul>
                                <li><strong>Upload a roster:</strong> Use the roster upload option for a full class list.</li>
                                <li><strong>Add one student:</strong> Use manual add when a new student joins later.</li>
                            </ul>
                        </li>
                        <li><strong>Share the class join code:</strong> Students use it once to enter the class and claim their seat.</li>
                    </ol>
                    <div class="alert alert-info">
                        <strong>Tip:</strong> Use the class you already selected for day-to-day work. If the wrong class is open, switch classes first.
                    </div>
                """
            },
            {
                "id": "managing_students",
                "title": "Manage Students",
                "content": """
                    <p>Use the Students area to keep your roster clean and current:</p>
                    <ul>
                        <li><strong>Add a student:</strong> Add a new student if they join your class later.</li>
                        <li><strong>Review a seat:</strong> Check whether a student has claimed their seat and is in the correct class.</li>
                        <li><strong>Remove a student:</strong> Deleting a seat removes the class link completely. Use it only when the student should no longer be part of that class.</li>
                        <li><strong>Fix a mismatch:</strong> If a student is in the wrong class, correct the class assignment instead of creating duplicate records.</li>
                    </ul>
                    <div class="alert alert-info">
                        <strong>Tip:</strong> If something looks wrong, check the student in the current class first. Most problems are caused by being in the wrong class view.
                    </div>
                """
            },
            {
                "id": "running_payroll",
                "title": "Run Payroll",
                "content": """
                    <p>Payroll pays students based on the class rules you set.</p>
                    <ul>
                        <li><strong>Run payroll:</strong> Open <strong>Payroll</strong> and start the run for the current class.</li>
                        <li><strong>Check settings:</strong> Review:
                            <ul>
                                <li><strong>Pay rate:</strong> how much students earn.</li>
                                <li><strong>Frequency:</strong> when payroll should run.</li>
                                <li><strong>Rules:</strong> any reward or fine settings that affect the result.</li>
                            </ul>
                        </li>
                        <li><strong>Review the result:</strong> Look for missing attendance or a class scope mismatch before rerunning payroll.</li>
                    </ul>
                """
            },
            {
                "id": "store_management",
                "title": "Manage Store Items",
                "content": """
                    <p>The store is where students spend class money.</p>
                    <ul>
                        <li><strong>Add items:</strong> Create a reward or item from the <strong>Store</strong> page.</li>
                        <li><strong>Set the rules:</strong> Decide:
                            <ul>
                                <li><strong>Price:</strong> how much the item costs.</li>
                                <li><strong>Availability:</strong> whether it can be bought now.</li>
                                <li><strong>Fulfillment:</strong> whether the item is immediate or needs teacher delivery.</li>
                            </ul>
                        </li>
                        <li><strong>Review redemptions:</strong> Finish delayed items after you hand them out.</li>
                    </ul>
                """
            },
            {
                "id": "insurance_policies",
                "title": "Use Rent and Insurance",
                "content": """
                    <p>Rent and insurance help you handle recurring charges and special protections.</p>
                    <ul>
                        <li><strong>Rent:</strong> Set the amount and timing for class rent.</li>
                        <li><strong>Insurance:</strong> Add policies that protect students from specific losses or fines.</li>
                        <li><strong>Claims:</strong> Review claims from the class view and decide whether to approve them.</li>
                    </ul>
                """
            },
            {
                "id": "banking_rent",
                "title": "Banking Basics",
                "content": """
                    <p>Use Banking to understand balances and keep money rules clear.</p>
                    <ul>
                        <li><strong>Balances:</strong> Checking is what students can spend now. Savings may earn interest if your class has it on.</li>
                        <li><strong>Interest:</strong> Check the active savings rule before you expect money to grow.</li>
                        <li><strong>Transfers:</strong> Use transfers only inside the correct class.</li>
                    </ul>
                """
            },
            {
                "id": "hall_passes",
                "title": "Hall Passes and Announcements",
                "content": """
                    <p>Use these tools to manage movement and class updates.</p>
                    <ul>
                        <li><strong>Hall passes:</strong> Review requests and approve them when the student is allowed to leave.</li>
                        <li><strong>Announcements:</strong> Share class updates that students need to see right away.</li>
                        <li><strong>Need help:</strong> Use the support page when the app behavior does not match what you expected.</li>
                    </ul>
                """
            }
        ],
        "troubleshooting": [
            {
                "id": "student_login_issues",
                "title": "A student cannot join",
                "content": """
                    <p>Check these in order:</p>
                    <ol>
                        <li><strong>Class code:</strong> Make sure the student is using the correct class join code.</li>
                        <li><strong>Current class:</strong> Confirm you are looking at the right class when you review the roster.</li>
                        <li><strong>Seat status:</strong> If the seat is already claimed, the student should use the seat they already claimed instead of starting over.</li>
                    </ol>
                """
            },
            {
                "id": "missing_pay",
                "title": "Payroll looks wrong",
                "content": """
                    <p>If a student did not get paid, check these first:</p>
                    <ul>
                        <li><strong>Attendance:</strong> Does the student have the attendance record expected by the current class payroll settings?</li>
                        <li><strong>Class scope:</strong> Are you viewing the correct class?</li>
                        <li><strong>Payroll settings:</strong> Is the active pay rate turned on?</li>
                        <li><strong>Support:</strong> If the result still looks wrong, submit a support ticket with the class, date, and what you expected.</li>
                    </ul>
                """
            }
        ]
    },
    "student": {
        "how_to": [
            {
                "id": "student_dashboard",
                "title": "Start Here",
                "content": """
                    <p>Your dashboard is the fastest place to check your class work.</p>
                    <ul>
                        <li><strong>Your class:</strong> Make sure you are in the right class first.</li>
                        <li><strong>Your balance:</strong> See what you can spend and what is in savings.</li>
                        <li><strong>Your status:</strong> Check whether you are signed in and active for class.</li>
                    </ul>
                """
            },
            {
                "id": "earning_spending",
                "title": "Earning and Spending",
                "content": """
                    <p>You earn money by following the class rules and taking part in class.</p>
                    <ul>
                        <li><strong>Spend money:</strong> Open the store to buy items your teacher has made available.</li>
                        <li><strong>Immediate items:</strong> You get them right away.</li>
                        <li><strong>Delayed items:</strong> Your teacher gives them to you later.</li>
                    </ul>
                """
            },
            {
                "id": "paying_bills",
                "title": "Pay Rent",
                "content": """
                    <p>If your class charges rent, you will see it in the app.</p>
                    <ul>
                        <li><strong>Check the due date:</strong> Look at the rent section before the deadline.</li>
                        <li><strong>Pay early:</strong> If you have enough checking money, you can pay before it is due.</li>
                        <li><strong>Need help:</strong> Ask your teacher if the rent amount or timing looks wrong.</li>
                    </ul>
                """
            },
            {
                "id": "insurance_help",
                "title": "Use Insurance",
                "content": """
                    <p>Insurance can help protect you from certain class charges or losses.</p>
                    <ul>
                        <li><strong>Check your options:</strong> Open the insurance area to see what your teacher offers.</li>
                        <li><strong>File a claim:</strong> Send a claim when something covered happens.</li>
                        <li><strong>Wait for review:</strong> Your teacher decides whether the claim is approved.</li>
                    </ul>
                """
            },
            {
                "id": "manage_classes",
                "title": "Switch Classes",
                "content": """
                    <p>If you have more than one class, you can switch between them.</p>
                    <ul>
                        <li><strong>Use the class switcher:</strong> Pick the class you want from the class list.</li>
                        <li><strong>Use the correct class:</strong> Most problems happen when the wrong class is selected.</li>
                    </ul>
                """
            }
        ],
        "troubleshooting": [
            {
                "id": "forgot_pin",
                "title": "I cannot sign in",
                "content": """
                    <p>Ask your teacher for help. They can help you get back into the right class or reset your access if needed.</p>
                """
            },
            {
                "id": "cant_buy",
                "title": "I cannot buy an item",
                "content": """
                    <p>Check these three things:</p>
                    <ol>
                        <li><strong>Money:</strong> Do you have enough in checking?</li>
                        <li><strong>Availability:</strong> Is the item still available?</li>
                        <li><strong>Limit:</strong> Did you already buy the maximum amount?</li>
                    </ol>
                """
            },
            {
                "id": "no_pay",
                "title": "I did not get paid",
                "content": """
                    <p>Payroll depends on the class rules and your attendance.</p>
                    <ul>
                        <li>Make sure you were in the correct class.</li>
                        <li>Check whether the class uses attendance or work time for payroll.</li>
                        <li>Ask your teacher to review it if it still looks wrong.</li>
                    </ul>
                """
            }
        ]
    }
}
