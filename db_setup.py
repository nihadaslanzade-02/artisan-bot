#!/usr/bin/env python
"""
Database setup script for Artisan Booking Bot.
This script creates or updates the database schema.
"""

import psycopg2
from config import DB_CONFIG

def setup_database():
    """Set up the database schema"""
    conn = None
    try:
        # Connect to the database
        print("Connecting to PostgreSQL database...")
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Create tables if they don't exist
        print("Creating tables if they don't exist...")
        
        # Customers table - updated with phone and city validation
        cur.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(20),
                city VARCHAR(50),
                email VARCHAR(100),
                address TEXT,
                profile_complete BOOLEAN DEFAULT FALSE,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Services table (main service categories)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE,
                description TEXT,
                icon VARCHAR(50),
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Subservices table (specific services under categories)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS subservices (
                id SERIAL PRIMARY KEY,
                service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(service_id, name)
            )
        ''')
        
        

        # Artisans table - updated with blocking fields and additional info
        cur.execute('''
            CREATE TABLE IF NOT EXISTS artisans (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) NOT NULL,
                service VARCHAR(50) NOT NULL,
                location VARCHAR(100),
                city VARCHAR(50),
                address TEXT,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                rating NUMERIC(2,1) DEFAULT 0,
                active BOOLEAN DEFAULT TRUE,
                blocked BOOLEAN DEFAULT FALSE,
                block_reason TEXT,
                block_time TIMESTAMP,
                payment_card_number VARCHAR(30),
                payment_card_holder VARCHAR(100),
                profile_complete BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        


        cur.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                artisan_id INTEGER NOT NULL REFERENCES artisans(id) ON DELETE CASCADE,
                service VARCHAR(50) NOT NULL,
                subservice VARCHAR(100),
                date_time TIMESTAMP NOT NULL,
                note TEXT,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                location_name VARCHAR(100),
                price NUMERIC(10,2),
                status VARCHAR(20) DEFAULT 'pending',
                payment_method VARCHAR(20),
                payment_status VARCHAR(20) DEFAULT 'unpaid',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')

        # Artisan blocks table - for keeping track of block history
        cur.execute('''
            CREATE TABLE IF NOT EXISTS artisan_blocks (
                id SERIAL PRIMARY KEY,
                artisan_id INTEGER NOT NULL REFERENCES artisans(id) ON DELETE CASCADE,
                is_blocked BOOLEAN DEFAULT TRUE,
                block_reason TEXT,
                required_payment NUMERIC(10,2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                unblocked_at TIMESTAMP
            )
        ''')


        # Create scheduled_tasks table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id SERIAL PRIMARY KEY,
                task_type VARCHAR(50) NOT NULL,
                reference_id INTEGER NOT NULL,
                execution_time TIMESTAMP NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                additional_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Create receipt_verification_history table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS receipt_verification_history (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                is_verified BOOLEAN NOT NULL,
                attempt_number INTEGER DEFAULT 1,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Artisan services table - to track which subservices each artisan provides
        cur.execute('''
            CREATE TABLE IF NOT EXISTS artisan_services (
                id SERIAL PRIMARY KEY,
                artisan_id INTEGER NOT NULL REFERENCES artisans(id) ON DELETE CASCADE,
                subservice_id INTEGER NOT NULL REFERENCES subservices(id) ON DELETE CASCADE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(artisan_id, subservice_id)
            )
        ''')
        
        # Artisan price ranges table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS artisan_price_ranges (
                id SERIAL PRIMARY KEY,
                artisan_id INTEGER NOT NULL REFERENCES artisans(id) ON DELETE CASCADE,
                subservice_id INTEGER NOT NULL REFERENCES subservices(id) ON DELETE CASCADE,
                min_price NUMERIC(10,2) NOT NULL,
                max_price NUMERIC(10,2) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(artisan_id, subservice_id)
            )
        ''')
        
        

        cur.execute('''
            CREATE TABLE IF NOT EXISTS notification_log (
                id SERIAL PRIMARY KEY,
                notification_type VARCHAR(50) NOT NULL,
                target_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS customer_blocks (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                is_blocked BOOLEAN DEFAULT TRUE,
                block_reason TEXT,
                required_payment NUMERIC(10,2) DEFAULT 0,
                block_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                unblocked_at TIMESTAMP
            )
        ''')
        
        # Order subservices table (links orders to specific subservices)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS order_subservices (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                subservice_id INTEGER NOT NULL REFERENCES subservices(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(order_id, subservice_id)
            )
        ''')
        
        # Order payments table - enhanced with more details
        cur.execute('''
            CREATE TABLE IF NOT EXISTS order_payments (
                id SERIAL PRIMARY KEY,
                order_id INTEGER UNIQUE NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                amount NUMERIC(10,2) NOT NULL,
                admin_fee NUMERIC(10,2) NOT NULL,
                artisan_amount NUMERIC(10,2) NOT NULL,
                payment_status VARCHAR(20) DEFAULT 'pending',
                payment_method VARCHAR(50),
                payment_date TIMESTAMP,
                receipt_file_id VARCHAR(255),
                receipt_uploaded_at TIMESTAMP,
                receipt_verified BOOLEAN DEFAULT FALSE,
                admin_payment_deadline TIMESTAMP,
                admin_payment_completed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Fine receipts table - for storing admin payment receipts
        cur.execute('''
            CREATE TABLE IF NOT EXISTS fine_receipts (
                id SERIAL PRIMARY KEY,
                artisan_id INTEGER NOT NULL REFERENCES artisans(id) ON DELETE CASCADE,
                file_id VARCHAR(255) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                verified_by INTEGER,
                verified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Reviews table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                artisan_id INTEGER NOT NULL REFERENCES artisans(id) ON DELETE CASCADE,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User context table - for temporary user data storage
        cur.execute('''
            CREATE TABLE IF NOT EXISTS user_context (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE,
                context_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        
        
        # Add indexes for performance
        print("Creating indexes...")
        # Customer indexes
        cur.execute('CREATE INDEX IF NOT EXISTS idx_customers_telegram ON customers (telegram_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers (phone)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_customers_city ON customers (city)')
        
        # Artisan indexes
        cur.execute('CREATE INDEX IF NOT EXISTS idx_artisans_telegram ON artisans (telegram_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_artisans_phone ON artisans (phone)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_artisans_city ON artisans (city)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_artisans_service ON artisans (service)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_artisans_location ON artisans (latitude, longitude)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_artisans_blocked ON artisans (blocked)')
        
        # Services indexes
        cur.execute('CREATE INDEX IF NOT EXISTS idx_services_active ON services (active)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_subservices_service ON subservices (service_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_subservices_active ON subservices (active)')
        
        # Artisan services indexes
        cur.execute('CREATE INDEX IF NOT EXISTS idx_artisan_services_artisan ON artisan_services (artisan_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_artisan_services_subservice ON artisan_services (subservice_id)')
        
        # Price ranges indexes
        cur.execute('CREATE INDEX IF NOT EXISTS idx_artisan_price_ranges_artisan ON artisan_price_ranges (artisan_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_artisan_price_ranges_subservice ON artisan_price_ranges (subservice_id)')
        
        # Order indexes
        cur.execute('CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders (customer_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_orders_artisan ON orders (artisan_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_orders_datetime ON orders (date_time)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_orders_payment_status ON orders (payment_status)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_orders_payment_method ON orders (payment_method)')
        
        # Payment indexes
        cur.execute('CREATE INDEX IF NOT EXISTS idx_order_payments_status ON order_payments (payment_status)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_order_payments_method ON order_payments (payment_method)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_fine_receipts_artisan ON fine_receipts (artisan_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_fine_receipts_status ON fine_receipts (status)')
        
        # Update existing orders with default status if needed
        cur.execute("UPDATE orders SET status = 'pending' WHERE status IS NULL")
        cur.execute("UPDATE orders SET payment_status = 'unpaid' WHERE payment_status IS NULL")
        
        # Add city column to artisans table if it doesn't exist
        try:
            cur.execute("ALTER TABLE artisans ADD COLUMN IF NOT EXISTS city VARCHAR(50)")
        except psycopg2.Error:
            conn.rollback()
            print("Column 'city' might already exist in artisans table.")
        
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
            cur.execute(
                "INSERT INTO services (name, description) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
                (service_name, service_desc)
            )
        
        # Get service IDs
        cur.execute("SELECT id, name FROM services")
        service_ids = {name: id for id, name in cur.fetchall()}
        
        # Insert sample subservices
        print("Adding sample subservices if they don't exist...")
        
        # Santexnik subservices
        santexnik_subservices = [
            ('Su borusu təmiri', 'Su borularının təmiri və dəyişdirilməsi'),
            ('Kanalizasiya təmizlənməsi', 'Kanalizasiya boruları və sistemlərinin təmizlənməsi'),
            ('Krant quraşdırma', 'Krant və şlanqların quraşdırılması və təmiri'),
            ('Unitaz təmiri', 'Unitazların quraşdırılması və təmiri'),
            ('Hamam aksessuarlarının montajı', 'Hamam dəsti və aksessuarlarının quraşdırılması')
        ]
        
        for name, desc in santexnik_subservices:
            cur.execute(
                "INSERT INTO subservices (service_id, name, description) VALUES (%s, %s, %s) ON CONFLICT (service_id, name) DO NOTHING",
                (service_ids.get('Santexnik'), name, desc)
            )
        
        # Elektrik subservices
        elektrik_subservices = [
            ('Elektrik xəttinin çəkilişi', 'Elektrik xətlərinin çəkilişi və yenilənməsi'),
            ('Ruzetka və açar təmiri', 'Ruzetka və açarların quraşdırılması və təmiri'),
            ('İşıqlandırma quraşdırılması', 'Lampalar və işıqlandırma sistemlərinin quraşdırılması'),
            ('Elektrik avadanlıqlarının montajı', 'Elektrik avadanlıqlarının montajı və təmiri')
        ]
        
        for name, desc in elektrik_subservices:
            cur.execute(
                "INSERT INTO subservices (service_id, name, description) VALUES (%s, %s, %s) ON CONFLICT (service_id, name) DO NOTHING",
                (service_ids.get('Elektrik'), name, desc)
            )
        
        # Kombi ustası subservices
        kombi_subservices = [
            ('Kombi quraşdırılması', 'Kombilərin quraşdırılması və işə salınması'),
            ('Kombi təmiri', 'Kombilərin təmiri və ehtiyat hissələrinin dəyişdirilməsi'),
            ('Kombi təmizlənməsi və servis', 'Kombilərin təmizlənməsi və dövri servis xidməti'),
            ('Qaz xəttinə qoşulma', 'Qaz xəttinə qoşulma və təhlükəsizlik tədbirləri')
        ]
        
        for name, desc in kombi_subservices:
            cur.execute(
                "INSERT INTO subservices (service_id, name, description) VALUES (%s, %s, %s) ON CONFLICT (service_id, name) DO NOTHING",
                (service_ids.get('Kombi ustası'), name, desc)
            )
        
        # Kondisioner ustası subservices
        kondisioner_subservices = [
            ('Kondisioner quraşdırılması', 'Kondisionerlərin quraşdırılması və işə salınması'),
            ('Kondisioner təmiri', 'Kondisionerlərin təmiri və nasazlıqların aradan qaldırılması'),
            ('Kondisioner yuyulması (servis)', 'Kondisionerlərin təmizlənməsi və dövri servis xidməti')
        ]
        
        for name, desc in kondisioner_subservices:
            cur.execute(
                "INSERT INTO subservices (service_id, name, description) VALUES (%s, %s, %s) ON CONFLICT (service_id, name) DO NOTHING",
                (service_ids.get('Kondisioner ustası'), name, desc)
            )
        
        # Mebel ustası subservices
        mebel_subservices = [
            ('Mebel təmiri', 'Mövcud mebellərin təmiri və bərpası'),
            ('Yeni mebel yığılması', 'Yeni mebellərin yığılması və quraşdırılması'),
            ('Sökülüb-yığılması (daşınma üçün)', 'Köçmə zamanı mebellərin sökülüb yenidən yığılması'),
            ('Mətbəx mebeli quraşdırılması', 'Mətbəx mebelinin ölçülərə uyğun quraşdırılması')
        ]
        
        for name, desc in mebel_subservices:
            cur.execute(
                "INSERT INTO subservices (service_id, name, description) VALUES (%s, %s, %s) ON CONFLICT (service_id, name) DO NOTHING",
                (service_ids.get('Mebel ustası'), name, desc)
            )
        
        # Qapı-pəncərə ustası subservices
        qapi_pencere_subservices = [
            ('PVC pəncərə quraşdırılması', 'PVC pəncərələrin quraşdırılması və nizamlanması'),
            ('Taxta qapı təmiri', 'Taxta qapıların təmiri və bərpası'),
            ('Alüminium sistemlər', 'Alüminium qapı və pəncərələrin quraşdırılması'),
            ('Kilid və mexanizmlərin təmiri', 'Qapı kilidləri və mexanizmlərinin təmiri və dəyişdirilməsi')
        ]
        
        for name, desc in qapi_pencere_subservices:
            cur.execute(
                "INSERT INTO subservices (service_id, name, description) VALUES (%s, %s, %s) ON CONFLICT (service_id, name) DO NOTHING",
                (service_ids.get('Qapı-pəncərə ustası'), name, desc)
            )
        
        # Bərpa ustası subservices
        berpa_subservices = [
            ('Ev təmiri', 'Evlərin ümumi təmiri və yenilənməsi'),
            ('Divar kağızı (oboy) vurulması', 'Divar kağızlarının vurulması və hazırlıq işləri'),
            ('Rəngsaz işləri', 'Divar, tavan və fasadların rənglənməsi'),
            ('Alçıpan montajı', 'Alçıpan konstruksiyalarının quraşdırılması'),
            ('Döşəmə və laminat quraşdırılması', 'Döşəmə və laminatların quraşdırılması')
        ]
        
        for name, desc in berpa_subservices:
            cur.execute(
                "INSERT INTO subservices (service_id, name, description) VALUES (%s, %s, %s) ON CONFLICT (service_id, name) DO NOTHING",
                (service_ids.get('Bərpa ustası'), name, desc)
            )
        
        # Bağban subservices
        bagban_subservices = [
            ('Bağ sahəsinin təmizlənməsi', 'Bağ və həyət sahələrinin təmizlənməsi və hazırlanması'),
            ('Ağac budama', 'Ağacların budanması və baxımı'),
            ('Bağ suvarma sistemi qurulması', 'Avtomatik və ya manual suvarma sistemlərinin quraşdırılması'),
            ('Çəmən toxumu əkilməsi', 'Çəmən toxumunun səpilməsi və baxımı')
        ]
        
        for name, desc in bagban_subservices:
            cur.execute(
                "INSERT INTO subservices (service_id, name, description) VALUES (%s, %s, %s) ON CONFLICT (service_id, name) DO NOTHING",
                (service_ids.get('Bağban'), name, desc)
            )
        
        
        # Set up triggers for automatic timestamps
        cur.execute('''
            CREATE OR REPLACE FUNCTION update_timestamp()
            RETURNS TRIGGER AS $$
            BEGIN
               NEW.updated_at = NOW(); 
               RETURN NEW;
            END;
            $$ language 'plpgsql';
        ''')
        
        # Create triggers for all tables with updated_at
        for table in ['customers', 'artisans', 'orders', 'order_payments', 'artisan_price_ranges', 'user_context']:
            try:
                cur.execute(f'''
                    DROP TRIGGER IF EXISTS update_{table}_timestamp ON {table};
                    CREATE TRIGGER update_{table}_timestamp
                    BEFORE UPDATE ON {table}
                    FOR EACH ROW
                    EXECUTE PROCEDURE update_timestamp();
                ''')
            except psycopg2.Error as e:
                conn.rollback()
                print(f"Error creating trigger for {table}: {e}")
        
        print("Database setup completed successfully!")
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    setup_database()