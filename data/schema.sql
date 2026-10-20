-- Generated PostgreSQL schema for review. Use python -m app.seed for idempotent setup.


CREATE TABLE conversations (
	id VARCHAR(36) NOT NULL, 
	requirements JSONB NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE products (
	id VARCHAR(40) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	category VARCHAR(20) NOT NULL, 
	price_paise INTEGER NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	specifications JSONB NOT NULL, 
	intended_uses JSONB NOT NULL, 
	features JSONB NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_positive_price CHECK (price_paise >= 0), 
	CONSTRAINT ck_category CHECK (category IN ('laptop', 'headphones')), 
	CONSTRAINT ck_currency CHECK (currency = 'INR')
)

;

CREATE INDEX ix_product_category_price_id ON products (category, price_paise, id);


CREATE TABLE messages (
	id VARCHAR(36) NOT NULL, 
	conversation_id VARCHAR(36) NOT NULL, 
	role VARCHAR(12) NOT NULL, 
	content TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_message_role CHECK (role IN ('user', 'assistant', 'system')), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_message_conversation_time ON messages (conversation_id, created_at, id);
