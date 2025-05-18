#!/usr/bin/env python
"""
Database setup script for Artisan Booking Bot.
This script creates or updates the database schema for MySQL.
"""
import mysql.connector
import logging
from mysql.connector import Error
from config import DB_CONFIG
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_database():
    """Set up the database schema for MySQL"""
    conn = None
    try:
        # Connect to the database
        print("Connecting to MySQL database...")
        conn = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            port=DB_CONFIG.get("port", 3306)
        )
        
        # Enable autocommit
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        print("Creating tables if they don't exist...")
        
        # Customers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id VARCHAR(255) UNIQUE,
                name VARCHAR(500) NOT NULL UNIQUE,
                phone TEXT,
                city TEXT,
                email TEXT,
                address TEXT,
                profile_complete TINYINT(1) DEFAULT 0,
                active TINYINT(1) DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Services table (main service categories)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(500) NOT NULL UNIQUE,
                description TEXT,
                icon TEXT,
                active TINYINT(1) DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Subservices table (specific services under categories)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subservices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                service_id INT NOT NULL,
                name VARCHAR(500) NOT NULL,
                description TEXT,
                active TINYINT(1) DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_service_name (service_id, name),
                FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Artisans table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artisans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id VARCHAR(255) UNIQUE,
                telegram_id_hash VARCHAR(255) UNIQUE,
                name VARCHAR(500) NOT NULL,
                phone TEXT NOT NULL,
                service TEXT NOT NULL,
                location TEXT,
                city TEXT,
                address TEXT,
                latitude DOUBLE,
                longitude DOUBLE,
                rating DECIMAL(2,1) DEFAULT 0,
                active TINYINT(1) DEFAULT 1,
                blocked TINYINT(1) DEFAULT 0,
                block_reason TEXT,
                block_time DATETIME,
                payment_card_number TEXT,
                payment_card_holder TEXT,
                profile_complete TINYINT(1) DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_id INT NOT NULL,
                artisan_id INT,
                service TEXT NOT NULL,
                subservice TEXT,
                date_time DATETIME NOT NULL,
                note TEXT,
                latitude DOUBLE,
                longitude DOUBLE,
                location_name TEXT,
                price DECIMAL(10,2),
                status VARCHAR(500) DEFAULT 'pending',
                payment_method TEXT,
                payment_status VARCHAR(500) DEFAULT 'unpaid',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                completed_at DATETIME,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                FOREIGN KEY (artisan_id) REFERENCES artisans(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')

        # Artisan blocks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artisan_blocks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                artisan_id INT NOT NULL,
                is_blocked TINYINT(1) DEFAULT 1,
                block_reason TEXT,
                required_payment DECIMAL(10,2) DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                unblocked_at DATETIME,
                FOREIGN KEY (artisan_id) REFERENCES artisans(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')

        # Scheduled tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_type TEXT NOT NULL,
                reference_id INT NOT NULL,
                execution_time DATETIME NOT NULL,
                status VARCHAR(500) DEFAULT 'pending',
                additional_data JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                started_at DATETIME,
                completed_at DATETIME
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')

        # Receipt verification history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS receipt_verification_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT NOT NULL,
                is_verified TINYINT(1) NOT NULL,
                attempt_number INT DEFAULT 1,
                verified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Artisan services table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artisan_services (
                id INT AUTO_INCREMENT PRIMARY KEY,
                artisan_id INT NOT NULL,
                subservice_id INT NOT NULL,
                is_active TINYINT(1) DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_artisan_subservice (artisan_id, subservice_id),
                FOREIGN KEY (artisan_id) REFERENCES artisans(id) ON DELETE CASCADE,
                FOREIGN KEY (subservice_id) REFERENCES subservices(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Artisan price ranges table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artisan_price_ranges (
                id INT AUTO_INCREMENT PRIMARY KEY,
                artisan_id INT NOT NULL,
                subservice_id INT NOT NULL,
                min_price DECIMAL(10,2) NOT NULL,
                max_price DECIMAL(10,2) NOT NULL,
                is_active TINYINT(1) DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_artisan_subservice_price (artisan_id, subservice_id),
                FOREIGN KEY (artisan_id) REFERENCES artisans(id) ON DELETE CASCADE,
                FOREIGN KEY (subservice_id) REFERENCES subservices(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Notification log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notification_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                notification_type TEXT NOT NULL,
                target_id INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')

        # Customer blocks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_blocks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_id INT NOT NULL,
                is_blocked TINYINT(1) DEFAULT 1,
                block_reason TEXT,
                required_payment DECIMAL(10,2) DEFAULT 0,
                block_until DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                unblocked_at DATETIME,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Order subservices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_subservices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT NOT NULL,
                subservice_id INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_order_subservice (order_id, subservice_id),
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (subservice_id) REFERENCES subservices(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Order payments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT NOT NULL UNIQUE,
                amount DECIMAL(10,2) NOT NULL,
                admin_fee DECIMAL(10,2) NOT NULL,
                artisan_amount DECIMAL(10,2) NOT NULL,
                payment_status TEXT,
                payment_method TEXT,
                payment_date DATETIME,
                receipt_file_id TEXT,
                receipt_uploaded_at DATETIME,
                receipt_verified TINYINT(1) DEFAULT 0,
                admin_payment_deadline DATETIME,
                admin_payment_completed TINYINT(1) DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Fine receipts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fine_receipts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                artisan_id INT NOT NULL,
                file_id TEXT NOT NULL,
                status VARCHAR(500) DEFAULT 'pending',
                verified_by INT,
                verified_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (artisan_id) REFERENCES artisans(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Reviews table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT NOT NULL,
                customer_id INT NOT NULL,
                artisan_id INT NOT NULL,
                rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
                comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                FOREIGN KEY (artisan_id) REFERENCES artisans(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # User context table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_context (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id VARCHAR(255) UNIQUE,
                context_data JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Create indexes for better performance
        print("Creating indexes...")
        
        # Customer indexes
        try:
            # Customer indexes
            cursor.execute('CREATE INDEX idx_customers_telegram ON customers (telegram_id)')
            cursor.execute('CREATE INDEX idx_customers_phone ON customers (phone(20))')  # burada uzunluq təyin edilib
            cursor.execute('CREATE INDEX idx_customers_city ON customers (city(20))')    # burada uzunluq təyin edilib
        except Error as e:
            logger.error(f"Error creating customer indexes: {e}")
        
        try:
            # Artisan indexes
            cursor.execute('CREATE INDEX idx_artisans_telegram ON artisans (telegram_id)')
            cursor.execute('CREATE INDEX idx_artisans_phone ON artisans (phone(20))')     # burada uzunluq təyin edilib
            cursor.execute('CREATE INDEX idx_artisans_city ON artisans (city(20))')       # burada uzunluq təyin edilib
            cursor.execute('CREATE INDEX idx_artisans_service ON artisans (service(20))') # burada uzunluq təyin edilib
            cursor.execute('CREATE INDEX idx_artisans_location ON artisans (latitude, longitude)')
            cursor.execute('CREATE INDEX idx_artisans_blocked ON artisans (blocked)')
        except Error as e:
            logger.error(f"Error creating artisan indexes: {e}")
        
        # Services indexes - TEXT sütunlar üçün açar uzunluğu əlavə et
        cursor.execute('CREATE INDEX idx_services_active ON services (active)')
        cursor.execute('CREATE INDEX idx_subservices_service ON subservices (service_id)')
        cursor.execute('CREATE INDEX idx_subservices_active ON subservices (active)')
        
        # Order indexes - TEXT sütunlar üçün açar uzunluğu əlavə et
        cursor.execute('CREATE INDEX idx_orders_customer ON orders (customer_id)')
        cursor.execute('CREATE INDEX idx_orders_artisan ON orders (artisan_id)')
        cursor.execute('CREATE INDEX idx_orders_status ON orders (status(20))')  # TEXT sütunu üçün uzunluq əlavə edildi
        cursor.execute('CREATE INDEX idx_orders_datetime ON orders (date_time)')
        cursor.execute('CREATE INDEX idx_orders_payment_status ON orders (payment_status(20))')  # TEXT sütunu üçün uzunluq əlavə edildi
        cursor.execute('CREATE INDEX idx_orders_payment_method ON orders (payment_method(20))')  # TEXT sütunu üçün uzunluq əlavə edildi
        
        # Payment indexes - TEXT sütunlar üçün açar uzunluğu əlavə et
        cursor.execute('CREATE INDEX idx_order_payments_status ON order_payments (payment_status(20))')  # TEXT sütunu üçün uzunluq əlavə edildi
        cursor.execute('CREATE INDEX idx_order_payments_method ON order_payments (payment_method(20))')  # TEXT sütunu üçün uzunluq əlavə edildi
        cursor.execute('CREATE INDEX idx_fine_receipts_artisan ON fine_receipts (artisan_id)')
        cursor.execute('CREATE INDEX idx_fine_receipts_status ON fine_receipts (status(20))')  # TEXT sütunu üçün uzunluq əlavə edildi
        
        # Update existing orders status if needed
        cursor.execute("UPDATE orders SET status = 'pending' WHERE status IS NULL")
        cursor.execute("UPDATE orders SET payment_status = 'unpaid' WHERE payment_status IS NULL")
        
        # Insert sample services if they don't exist
        print("Adding sample services if they don't exist...")
        service_data = [
            ('Santexnik', 'Su və kanalizasiya sistemləri ilə bağlı xidmətlər'),
            ('Elektrik', 'Elektrik sistemləri ilə bağlı xidmətlər'),
            ('Kombi ustası', 'İstilik sistemləri ilə bağlı xidmətlər'),
            ('Kondisioner ustası', 'Kondisioner sistemləri ilə bağlı xidmətlər'),
            ('Mebel ustası', 'Mebel quraşdırılması və təmiri xidmətləri'),
            ('Qapı-pəncərə ustası', 'Qapı və pəncərə sistemləri ilə bağlı xidmətlər'),
            ('Bərpa ustası', 'Ev təmiri və bərpası xidmətləri'),
            ('Bağban', 'Bağ və həyət işləri ilə bağlı xidmətlər')
        ]
        
        for service_name, service_desc in service_data:
            try:
                cursor.execute(
                    "INSERT IGNORE INTO services (name, description) VALUES (%s, %s)",
                    (service_name, service_desc)
                )
            except Error as e:
                print(f"Error inserting service {service_name}: {e}")
        
        # Get service IDs
        cursor.execute("SELECT id, name FROM services")
        service_ids = {name: id for id, name in cursor.fetchall()}
        
        # Insert sample subservices
        print("Adding sample subservices if they don't exist...")
        
        # Santexnik subservices
        if 'Santexnik' in service_ids:
            santexnik_subservices = [
                ('Su borusu təmiri', 'Su borularının təmiri və dəyişdirilməsi'),
                ('Kanalizasiya təmizlənməsi', 'Kanalizasiya boruları və sistemlərinin təmizlənməsi'),
                ('Krant quraşdırma', 'Krant və şlanqların quraşdırılması və təmiri'),
                ('Unitaz təmiri', 'Unitazların quraşdırılması və təmiri'),
                ('Hamam aksessuarlarının montajı', 'Hamam dəsti və aksessuarlarının quraşdırılması')
            ]
            
            for name, desc in santexnik_subservices:
                try:
                    cursor.execute(
                        "INSERT IGNORE INTO subservices (service_id, name, description) VALUES (%s, %s, %s)",
                        (service_ids['Santexnik'], name, desc)
                    )
                except Error as e:
                    print(f"Error inserting subservice {name}: {e}")
        
        # Elektrik subservices
        if 'Elektrik' in service_ids:
            elektrik_subservices = [
                ('Elektrik xəttinin çəkilişi', 'Elektrik xətlərinin çəkilişi və yenilənməsi'),
                ('Ruzetka və açar təmiri', 'Ruzetka və açarların quraşdırılması və təmiri'),
                ('İşıqlandırma quraşdırılması', 'Lampalar və işıqlandırma sistemlərinin quraşdırılması'),
                ('Elektrik avadanlıqlarının montajı', 'Elektrik avadanlıqlarının montajı və təmiri')
            ]
            
            for name, desc in elektrik_subservices:
                try:
                    cursor.execute(
                        "INSERT IGNORE INTO subservices (service_id, name, description) VALUES (%s, %s, %s)",
                        (service_ids['Elektrik'], name, desc)
                    )
                except Error as e:
                    print(f"Error inserting subservice {name}: {e}")
        
        # Kombi ustası subservices
        if 'Kombi ustası' in service_ids:
            kombi_subservices = [
                ('Kombi quraşdırılması', 'Kombilərin quraşdırılması və işə salınması'),
                ('Kombi təmiri', 'Kombilərin təmiri və ehtiyat hissələrinin dəyişdirilməsi'),
                ('Kombi təmizlənməsi və servis', 'Kombilərin təmizlənməsi və dövri servis xidməti'),
                ('Qaz xəttinə qoşulma', 'Qaz xəttinə qoşulma və təhlükəsizlik tədbirləri')
            ]
            
            for name, desc in kombi_subservices:
                try:
                    cursor.execute(
                        "INSERT IGNORE INTO subservices (service_id, name, description) VALUES (%s, %s, %s)",
                        (service_ids['Kombi ustası'], name, desc)
                    )
                except Error as e:
                    print(f"Error inserting subservice {name}: {e}")
        
        # Kondisioner ustası subservices
        if 'Kondisioner ustası' in service_ids:
            kondisioner_subservices = [
                ('Kondisioner quraşdırılması', 'Kondisionerlərin quraşdırılması və işə salınması'),
                ('Kondisioner təmiri', 'Kondisionerlərin təmiri və nasazlıqların aradan qaldırılması'),
                ('Kondisioner yuyulması (servis)', 'Kondisionerlərin təmizlənməsi və dövri servis xidməti')
            ]
            
            for name, desc in kondisioner_subservices:
                try:
                    cursor.execute(
                        "INSERT IGNORE INTO subservices (service_id, name, description) VALUES (%s, %s, %s)",
                        (service_ids['Kondisioner ustası'], name, desc)
                    )
                except Error as e:
                    print(f"Error inserting subservice {name}: {e}")
        
        # Mebel ustası subservices
        if 'Mebel ustası' in service_ids:
            mebel_subservices = [
                ('Mebel təmiri', 'Mövcud mebellərin təmiri və bərpası'),
                ('Yeni mebel yığılması', 'Yeni mebellərin yığılması və quraşdırılması'),
                ('Sökülüb-yığılması (daşınma üçün)', 'Köçmə zamanı mebellərin sökülüb yenidən yığılması'),
                ('Mətbəx mebeli quraşdırılması', 'Mətbəx mebelinin ölçülərə uyğun quraşdırılması')
            ]
            
            for name, desc in mebel_subservices:
                try:
                    cursor.execute(
                        "INSERT IGNORE INTO subservices (service_id, name, description) VALUES (%s, %s, %s)",
                        (service_ids['Mebel ustası'], name, desc)
                    )
                except Error as e:
                    print(f"Error inserting subservice {name}: {e}")
        
        # Qapı-pəncərə ustası subservices
        if 'Qapı-pəncərə ustası' in service_ids:
            qapi_pencere_subservices = [
                ('PVC pəncərə quraşdırılması', 'PVC pəncərələrin quraşdırılması və nizamlanması'),
                ('Taxta qapı təmiri', 'Taxta qapıların təmiri və bərpası'),
                ('Alüminium sistemlər', 'Alüminium qapı və pəncərələrin quraşdırılması'),
                ('Kilid və mexanizmlərin təmiri', 'Qapı kilidləri və mexanizmlərinin təmiri və dəyişdirilməsi')
            ]
            
            for name, desc in qapi_pencere_subservices:
                try:
                    cursor.execute(
                        "INSERT IGNORE INTO subservices (service_id, name, description) VALUES (%s, %s, %s)",
                        (service_ids['Qapı-pəncərə ustası'], name, desc)
                    )
                except Error as e:
                    print(f"Error inserting subservice {name}: {e}")
        
        # Bərpa ustası subservices
        if 'Bərpa ustası' in service_ids:
            berpa_subservices = [
                ('Ev təmiri', 'Evlərin ümumi təmiri və yenilənməsi'),
                ('Divar kağızı (oboy) vurulması', 'Divar kağızlarının vurulması və hazırlıq işləri'),
                ('Rəngsaz işləri', 'Divar, tavan və fasadların rənglənməsi'),
                ('Alçıpan montajı', 'Alçıpan konstruksiyalarının quraşdırılması'),
                ('Döşəmə və laminat quraşdırılması', 'Döşəmə və laminatların quraşdırılması')
            ]
            
            for name, desc in berpa_subservices:
                try:
                    cursor.execute(
                        "INSERT IGNORE INTO subservices (service_id, name, description) VALUES (%s, %s, %s)",
                        (service_ids['Bərpa ustası'], name, desc)
                    )
                except Error as e:
                    print(f"Error inserting subservice {name}: {e}")
        
        # Bağban subservices
        if 'Bağban' in service_ids:
            bagban_subservices = [
                ('Bağ sahəsinin təmizlənməsi', 'Bağ və həyət sahələrinin təmizlənməsi və hazırlanması'),
                ('Ağac budama', 'Ağacların budanması və baxımı'),
                ('Bağ suvarma sistemi qurulması', 'Avtomatik və ya manual suvarma sistemlərinin quraşdırılması'),
                ('Çəmən toxumu əkilməsi', 'Çəmən toxumunun səpilməsi və baxımı')
            ]
            
            for name, desc in bagban_subservices:
                try:
                    cursor.execute(
                        "INSERT IGNORE INTO subservices (service_id, name, description) VALUES (%s, %s, %s)",
                        (service_ids['Bağban'], name, desc)
                    )
                except Error as e:
                    print(f"Error inserting subservice {name}: {e}")
        
        print("Database setup completed successfully!")
        
    except Error as error:
        print(f"Error: {error}")
    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()
            print("Database connection closed.")

    # Ensure telegram_id_hash column exists in customers
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE table_name = 'customers' AND column_name = 'telegram_id_hash'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE customers ADD COLUMN telegram_id_hash VARCHAR(255)")
            conn.commit()
    except Exception as e:
        print(f"Error ensuring telegram_id_hash column: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    setup_database()