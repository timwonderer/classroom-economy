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
                    <p>Welcome to the Classroom Economy! This platform helps you manage a simulated economy in your classroom. Here's how to get started:</p>
                    <ol>
                        <li><strong>Complete Onboarding:</strong> Follow the setup wizard to choose features and set up your first class period.</li>
                        <li><strong>Add Students:</strong> Upload a CSV roster or add students manually in the 'Students' tab.</li>
                        <li><strong>Print Join Codes:</strong> Each period has a unique Join Code. Share this with your students so they can claim their accounts.</li>
                    </ol>
                    <p>Once students claim their accounts, they will appear in your dashboard where you can track their balances and activity.</p>
                """
            },
            {
                "id": "managing_students",
                "title": "Managing Students",
                "content": """
                    <p>You can manage student accounts from the <strong>Students</strong> tab.</p>
                    <ul>
                        <li><strong>Add Students:</strong> Use 'Upload Roster' for bulk addition via CSV, or 'Add Student' for individuals.</li>
                        <li><strong>Edit Details:</strong> Click on a student's name to edit their details, reset their password, or change their block assignment.</li>
                        <li><strong>Delete:</strong> You can delete a student if they leave the class. This removes all their data.</li>
                    </ul>
                    <p><strong>Note:</strong> Students must claim their account using the Join Code before they can log in.</p>
                """
            },
            {
                "id": "running_payroll",
                "title": "Running Payroll",
                "content": """
                    <p>Payroll pays students for their attendance and participation.</p>
                    <ol>
                        <li>Go to the <strong>Payroll</strong> tab.</li>
                        <li>Review the 'Next Payroll' estimate.</li>
                        <li>Click <strong>Run Payroll</strong> to deposit funds into student checking accounts based on their attendance.</li>
                    </ol>
                    <p>You can configure pay rates and frequency in <strong>Payroll Settings</strong>. You can also issue one-time <strong>Bonuses</strong> or <strong>Fines</strong> from this page.</p>
                """
            },
            {
                "id": "store_management",
                "title": "Classroom Store",
                "content": """
                    <p>The Store allows students to spend their earnings on rewards.</p>
                    <ul>
                        <li><strong>Add Items:</strong> Go to the <strong>Store</strong> tab and click 'Add Item'. Set a price and inventory limit.</li>
                        <li><strong>Fulfill Orders:</strong> When students buy 'Delayed' items, they appear as 'Pending' on your dashboard. Click to mark them as fulfilled.</li>
                        <li><strong>Item Types:</strong>
                            <ul>
                                <li><em>Immediate:</em> Student gets the item right away (e.g., digital perk).</li>
                                <li><em>Delayed:</em> Requires teacher fulfillment (e.g., physical item).</li>
                            </ul>
                        </li>
                    </ul>
                """
            },
            {
                "id": "banking_rent",
                "title": "Banking & Rent",
                "content": """
                    <p><strong>Banking:</strong> Students have Checking and Savings accounts. You can set interest rates for savings in the <strong>Banking</strong> tab. Overdraft protection can also be enabled.</p>
                    <p><strong>Rent:</strong> You can charge students rent for their desks.</p>
                    <ul>
                        <li>Configure rent amount and due dates in <strong>Rent Settings</strong>.</li>
                        <li>Students pay rent from their dashboard.</li>
                        <li>You can issue <strong>Rent Waivers</strong> for students who need exemption.</li>
                    </ul>
                """
            },
            {
                "id": "insurance",
                "title": "Insurance",
                "content": """
                    <p>Insurance protects students from unexpected costs or fines.</p>
                    <ul>
                        <li>Create policies in the <strong>Insurance</strong> tab (e.g., "Health Insurance", "Theft Protection").</li>
                        <li>Set premiums and coverage terms.</li>
                        <li>Students purchase policies and file claims if an incident occurs.</li>
                        <li>You review and approve/reject claims from the dashboard.</li>
                    </ul>
                """
            }
        ],
        "troubleshooting": [
            {
                "id": "student_login",
                "title": "Student Can't Log In",
                "content": """
                    <p>If a student cannot log in:</p>
                    <ul>
                        <li><strong>Check Username:</strong> Ensure they are typing their username exactly as it appears in the 'Students' list.</li>
                        <li><strong>Reset Login:</strong> Go to the student's detail page and verify their account is claimed. If they forgot their PIN/Passphrase, you may need to reset their login so they can reclaim the account.</li>
                        <li><strong>Join Code:</strong> Verify they are using the correct Join Code for their class period.</li>
                    </ul>
                """
            },
            {
                "id": "wrong_balance",
                "title": "Student Balance Incorrect",
                "content": """
                    <p>If a student's balance seems wrong:</p>
                    <ul>
                        <li>Check <strong>Transactions</strong> in the Banking tab to see recent activity.</li>
                        <li>If a transaction was made in error, you can <strong>Void</strong> it from the transaction list.</li>
                        <li>You can use <strong>Manual Payment</strong> in the Payroll tab to adjust funds if needed.</li>
                    </ul>
                """
            },
            {
                "id": "payroll_zero",
                "title": "Payroll Amount is 0",
                "content": """
                    <p>If payroll calculates as 0 for a student:</p>
                    <ul>
                        <li>Check <strong>Attendance Logs</strong>. Payroll is based on time "tapped in".</li>
                        <li>If a student forgot to tap in, they won't accrue earnings.</li>
                        <li>Verify <strong>Payroll Settings</strong> to ensure the pay rate is set correctly (> 0).</li>
                    </ul>
                """
            }
        ]
    },
    "student": {
        "how_to": [
            {
                "id": "dashboard",
                "title": "Your Dashboard",
                "content": """
                    <p>Your Dashboard is your home base. Here you can see:</p>
                    <ul>
                        <li><strong>Checking Balance:</strong> Money you can spend right now.</li>
                        <li><strong>Savings Balance:</strong> Money you are saving for later (it earns interest!).</li>
                        <li><strong>Attendance:</strong> Shows if you are currently "Tapped In" to class.</li>
                        <li><strong>Alerts:</strong> Notifications about bills or messages from your teacher.</li>
                    </ul>
                """
            },
            {
                "id": "earning_money",
                "title": "Earning Money",
                "content": """
                    <p>You earn money by attending class and doing your job.</p>
                    <ul>
                        <li><strong>Tap In:</strong> Make sure to "Tap In" when you arrive at class using the class terminal.</li>
                        <li><strong>Payroll:</strong> Your teacher will run payroll regularly. The money will go into your Checking account.</li>
                        <li><strong>Bonuses:</strong> You might earn extra money for good behavior or special achievements!</li>
                    </ul>
                """
            },
            {
                "id": "spending_money",
                "title": "Spending Money",
                "content": """
                    <p>Visit the <strong>Shop</strong> to buy cool items!</p>
                    <ul>
                        <li>Browse items your teacher has listed.</li>
                        <li>Click "Buy" to purchase. The money comes from your Checking account.</li>
                        <li>Some items are given immediately, others might need your teacher to hand them to you later.</li>
                    </ul>
                    <p>You can also move money to <strong>Savings</strong> to earn more money over time (Interest).</p>
                """
            },
            {
                "id": "bills_insurance",
                "title": "Bills & Insurance",
                "content": """
                    <p>Just like in real life, you have expenses.</p>
                    <ul>
                        <li><strong>Rent:</strong> You may need to pay rent for your desk. Check the <strong>Rent</strong> tab to see when it's due. Pay it on time to avoid late fees!</li>
                        <li><strong>Insurance:</strong> You can buy insurance to protect yourself from fines or accidents. Visit the <strong>Insurance</strong> tab to see available plans.</li>
                    </ul>
                """
            }
        ],
        "troubleshooting": [
            {
                "id": "forgot_pin",
                "title": "I forgot my PIN or Password",
                "content": """
                    <p>Don't panic! Ask your teacher for help. They can look up your username or reset your account login so you can set a new PIN.</p>
                """
            },
            {
                "id": "didnt_get_paid",
                "title": "I didn't get paid",
                "content": """
                    <p>Payroll is based on your attendance.</p>
                    <ul>
                        <li>Did you remember to <strong>Tap In</strong> when class started?</li>
                        <li>Check your <strong>Attendance</strong> status on the dashboard.</li>
                        <li>If you think there is a mistake, ask your teacher politely to check the logs.</li>
                    </ul>
                """
            },
            {
                "id": "cant_buy",
                "title": "I can't buy an item",
                "content": """
                    <p>If you can't buy something, check:</p>
                    <ul>
                        <li><strong>Balance:</strong> Do you have enough money in your <em>Checking</em> account? Savings money can't be spent directly.</li>
                        <li><strong>Stock:</strong> Is the item out of stock?</li>
                        <li><strong>Limit:</strong> Have you bought the maximum amount allowed for that item?</li>
                    </ul>
                """
            }
        ]
    }
}
