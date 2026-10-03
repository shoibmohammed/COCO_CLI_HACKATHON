variable "snowflake_account" {
  type        = string
  description = "Snowflake Account locator or identifier"
}

variable "snowflake_user" {
  type        = string
  description = "Snowflake administrative username"
}

variable "snowflake_password" {
  type        = string
  sensitive   = true
  description = "Snowflake user password"
}

variable "snowflake_role" {
  type        = string
  default     = "ACCOUNTADMIN"
  description = "Role used for Terraform provisioning"
}

variable "warehouse_name" {
  type        = string
  default     = "PM_OEE_WH"
  description = "Name of virtual warehouse"
}

variable "database_name" {
  type        = string
  default     = "PM_OEE_DB"
  description = "Name of database"
}

variable "schema_name" {
  type        = string
  default     = "CORE"
  description = "Name of application schema"
}
