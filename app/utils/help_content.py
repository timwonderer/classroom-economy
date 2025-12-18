"""
Help and support documentation content for Classroom Token Hub.
Structured for Teacher (General Adult) and Student (Middle School) audiences.
"""

HELP_ARTICLES = {
    "teacher": {
        "how_to": [
            {
                "id": "getting_started",
                "title": "Getting Started",
                "content": """
                    <p>Welcome to Classroom Token Hub! Follow these steps to set up your classroom economy:</p>
                    <ol>
                        <li><strong>Complete Onboarding:</strong> If you haven't already, the setup wizard will guide you through choosing features (Payroll, Store, etc.) and defining your class periods.</li>
                        <li><strong>Add Students:</strong> Go to the <strong>Students</strong> tab. You can:
                            <ul>
                                <li><strong>Upload Roster:</strong> Use the CSV template to upload your entire class list at once.</li>
                                <li><strong>Add Manually:</strong> Add students one by one if you have a small class or a new student joins.</li>
                            </ul>
                        </li>
                        <li><strong>Distribute Join Codes:</strong> Each period has a unique <strong>Join Code</strong> (visible on the Students tab). Share this with your students so they can claim their accounts.</li>
                    </ol>
                    <div class="alert alert-info">
                        <strong>Tip:</strong> Students must "claim" their accounts using the Join Code and their Name/DOB before they can log in.
                    </div>
                """
            },
            {
                "id": "managing_students",
                "title": "Managing Students",
                "content": """
                    <p>Manage your classroom roster efficiently with these tools:</p>
                    <ul>
                        <li><strong>Add Students:</strong> Go to the <strong>Students</strong> tab and click "Add Student". Enter the student's name, date of birth, and assign them to a class period. You can add students individually or use the "Bulk Add" option to paste a list.</li>
                        <li><strong>Edit Students:</strong> In the <strong>Students</strong> tab, find the student you wish to edit and click the "Edit" (pencil) icon. Update their information as needed and save your changes.</li>
                        <li><strong>Delete Students:</strong> To remove a student, click the "Delete" (trash) icon next to their name. <span class="text-danger">Warning:</span> Deleting a student will permanently remove their account and all associated data.</li>
                        <li><strong>Reset Join Codes:</strong> If a student is having trouble joining, you can reset their join code from the student's options menu.</li>
                    </ul>
                    <div class="alert alert-info">
                        <strong>Tip:</strong> Encourage students to claim their accounts promptly using the join code and their personal details.
                    </div>
                """
            },
            {
                "id": "running_payroll",
                "title": "Running Payroll",
                "content": """
                    <p>Payroll pays students based on their attendance. Here is how to manage it:</p>
                    <ul>
                        <li><strong>Run Payroll:</strong> Go to the <strong>Payroll</strong> tab and click "Run Payroll Now". The system calculates earnings based on attendance logs since the last run.</li>
                        <li><strong>Settings:</strong> Click "Manage Payroll Settings" to configure:
                            <ul>
                                <li><strong>Pay Rate:</strong> How much students earn per hour (or period).</li>
                                <li><strong>Frequency:</strong> How often payroll should run (e.g., Weekly, Bi-Weekly).</li>
                            </ul>
                        </li>
                        <li><strong>Bonuses & Fines:</strong> Use the "Rewards" and "Fines" sections to issue one-time payments or deductions to specific students or the whole class.</li>
                    </ul>
                """
            },
            {
                "id": "store_management",
                "title": "Classroom Store & Inventory",
                "content": """
                    <p>The Store allows students to spend their hard-earned money. Manage it from the <strong>Store</strong> tab:</p>
                    <ul>
                        <li><strong>Add Items:</strong> Click "Add Item" to create rewards. You can set:
                            <ul>
                                <li><strong>Inventory:</strong> Limit how many are available.</li>
                                <li><strong>Bundles:</strong> Create packs of items (e.g., "5 Homework Passes").</li>
                                <li><strong>Bulk Discounts:</strong> Offer lower prices for buying in bulk.</li>
                            </ul>
                        </li>
                        <li><strong>Fulfillment:</strong> When students buy "Delayed" items (physical goods), they appear in your <strong>Dashboard</strong> under "Pending Actions". Click "Approve" once you have delivered the item.</li>
                    </ul>
                """
            },
            {
                "id": "insurance_policies",
                "title": "Insurance Policies",
                "content": """
                    <p>Insurance helps students manage risk (e.g., fines, lost items).</p>
                    <ul>
                        <li><strong>Create Policies:</strong> Go to the <strong>Insurance</strong> tab and click "Create Policy".</li>
                        <li><strong>Grouped Policies:</strong> You can group policies (e.g., "Health Levels") so students can only choose one from that group.</li>
                        <li><strong>Claims:</strong> Students file claims from their portal. You review them on your <strong>Dashboard</strong> or the Insurance tab. You can approve (auto-pay) or reject claims.</li>
                    </ul>
                """
            },
            {
                "id": "banking_rent",
                "title": "Banking & Rent",
                "content": """
                    <p><strong>Banking:</strong> Manage interest and overdrafts in the <strong>Banking</strong> tab.</p>
                    <ul>
                        <li><strong>Interest:</strong> Set an APY (Annual Percentage Yield) or Monthly rate to encourage savings.</li>
                        <li><strong>Overdraft Protection:</strong> Enable this to allow savings to cover checking overdrafts automatically.</li>
                    </ul>
                    <p><strong>Rent:</strong> Charge students for their desks/seats.</p>
                    <ul>
                        <li><strong>Configure:</strong> Go to <strong>Rent Settings</strong> to set the amount and due dates.</li>
                        <li><strong>Waivers:</strong> You can exempt specific students from rent if needed.</li>
                    </ul>
                """
            },
            {
                "id": "hall_passes",
                "title": "Hall Passes",
                "content": """
                    <p>Manage student movement digitally:</p>
                    <ul>
                        <li><strong>Requests:</strong> Students request passes from a kiosk or their device.</li>
                        <li><strong>Approval:</strong> Requests appear in your <strong>Dashboard</strong> or the <strong>Hall Pass</strong> tab.</li>
                        <li><strong>Tracking:</strong> See who is currently "Out" and view history of all passes.</li>
                    </ul>
                """
            }
        ],
        "troubleshooting": [
            {
                "id": "student_login_issues",
                "title": "Student Cannot Log In",
                "content": """
                    <p>Common solutions:</p>
                    <ol>
                        <li><strong>Account Claimed?</strong> Check the student list. If their status is not "Active", they need to claim their account first using the Join Code.</li>
                        <li><strong>Wrong Username:</strong> Verify they are typing the username exactly as shown in your roster.</li>
                        <li><strong>Forgot PIN:</strong> Go to the student's profile and click "Reset Login". This will force them to re-claim their account and set a new PIN.</li>
                    </ol>
                """
            },
            {
                "id": "missing_pay",
                "title": "Payroll Seems Wrong",
                "content": """
                    <p>If a student didn't get paid:</p>
                    <ul>
                        <li><strong>Check Attendance:</strong> Payroll relies on "Start Work" records. If a student forgot to start working, they earned $0.</li>
                        <li><strong>Check Settings:</strong> Ensure your "Pay Rate" is greater than $0.</li>
                        <li><strong>Manual Adjustment:</strong> You can use the "Manual Payment" tool in the Payroll tab to fix any errors.</li>
                    </ul>
                """
            }
        ]
    },
    "student": {
        "how_to": [
            {
                "id": "student_dashboard",
                "title": "Your Dashboard",
                "content": """
                    <p>Your Dashboard is your command center. Here you can see:</p>
                    <ul>
                        <li><strong>Money:</strong> How much is in your <strong>Checking</strong> (spendable) and <strong>Savings</strong> (earning interest) accounts.</li>
                        <li><strong>Attendance:</strong> Are you "Tapped In"? Make sure you are to earn money!</li>
                        <li><strong>Alerts:</strong> Check here for rent bills or messages from your teacher.</li>
                    </ul>
                """
            },
            {
                "id": "earning_spending",
                "title": "Earning & Spending",
                "content": """
                    <p><strong>Earning:</strong> You earn money by coming to class and doing your job. Just remember to <strong>Tap In</strong> every day!</p>
                    <p><strong>Spending:</strong> Visit the <strong>Shop</strong> to buy rewards.</p>
                    <ul>
                        <li><strong>Immediate Items:</strong> You get these right away (like digital stickers).</li>
                        <li><strong>Delayed Items:</strong> Your teacher will bring these to you later (like a pencil or eraser).</li>
                    </ul>
                """
            },
            {
                "id": "paying_bills",
                "title": "Paying Rent & Bills",
                "content": """
                    <p>Part of growing up is paying bills!</p>
                    <ul>
                        <li><strong>Rent:</strong> Check the <strong>Rent</strong> tab to see when your payment is due.</li>
                        <li><strong>Pay Early:</strong> You can pay before the due date if you have the money.</li>
                        <li><strong>Late Fees:</strong> If you wait too long, you might have to pay extra!</li>
                    </ul>
                """
            },
            {
                "id": "insurance_help",
                "title": "Insurance",
                "content": """
                    <p>Protect your money with Insurance.</p>
                    <ul>
                        <li><strong>Buy Policy:</strong> Go to the <strong>Insurance</strong> tab to see plans your teacher offers.</li>
                        <li><strong>File a Claim:</strong> If something bad happens (like you get a fine), go to "My Policies" and click "File Claim". Your teacher will decide if insurance covers it.</li>
                    </ul>
                """
            },
            {
                "id": "manage_classes",
                "title": "Joining Multiple Classes",
                "content": """
                    <p>Do you have Classroom Token Hub in more than one class?</p>
                    <ul>
                        <li><strong>Add Class:</strong> Click "Add New Class" in the sidebar and enter the <strong>Join Code</strong> from your other teacher.</li>
                        <li><strong>Switching:</strong> You can switch between your classes anytime using the "Switch Class" button on your dashboard.</li>
                    </ul>
                """
            }
        ],
        "troubleshooting": [
            {
                "id": "forgot_pin",
                "title": "I forgot my PIN",
                "content": """
                    <p>It happens! Ask your teacher for help. They can reset your login so you can pick a new PIN.</p>
                """
            },
            {
                "id": "cant_buy",
                "title": "Why can't I buy this?",
                "content": """
                    <p>Check these three things:</p>
                    <ol>
                        <li><strong>Money:</strong> Do you have enough cash in your <em>Checking</em> account? (Savings doesn't count!)</li>
                        <li><strong>Inventory:</strong> Is the item sold out?</li>
                        <li><strong>Limit:</strong> Did you already buy the maximum amount allowed?</li>
                    </ol>
                """
            },
            {
                "id": "no_pay",
                "title": "I didn't get paid!",
                "content": """
                    <p>Payroll works by checking if you were in class.</p>
                    <ul>
                        <li>Did you <strong>Tap In</strong> when you arrived?</li>
                        <li>Check your attendance log. If you forgot to Start Work, tell your teacher nicely!</li>
                    </ul>
                """
            }
        ]
    }
}
