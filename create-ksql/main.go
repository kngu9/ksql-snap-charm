package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"sort"
	"strings"

	"github.com/pkg/errors"
	yaml "gopkg.in/yaml.v1"
)

type EntryType string

const (
	TableEntry     EntryType = "TABLE"
	StreamEntry    EntryType = "STREAM"
	StatementEntry EntryType = "STATEMENT"
)

type Config struct {
	Entries []Entry `yaml:"entries"`
}

type Entry struct {
	Description string    `yaml:"description"`
	Type        EntryType `yaml:"type"`
	Name        string    `yaml:"name,omitempty"`
	Base        bool      `yaml:"base,omitempty"`
	KSQL        string    `yaml:"ksql"`
}

type DescriptionResult struct {
	StatementText     string            `json:"statementText"`
	SourceDescription SourceDescription `json:"sourceDescription"`
}

type SourceDescription struct {
	Name         string       `json:"name"`
	Type         string       `json:"type"`
	Replication  int          `json:"replication"`
	Partitions   int          `json:"partitions"`
	ReadQueries  []ReadQuery  `json:"readQueries"`
	WriteQueries []WriteQuery `json:"writeQueries"`
	Fields       []Field      `json:"fields"`
}

type Field struct {
	Name   string      `json:"name"`
	Schema FieldSchema `json:"schema"`
}

type FieldSchema struct {
	Type string `json:"type"`
}

type ReadQuery struct {
	Id          string   `json:"id"`
	Sinks       []string `json:"sinks"`
	QueryString string   `json:"queryString"`
}

type WriteQuery struct {
	Id          string   `json:"id"`
	Sinks       []string `json:"sinks"`
	QueryString string   `json:"queryString"`
}

type client struct {
	url string
}

type commandStatus struct {
	Message string `json:"message"`
	Status  string `json:"success"`
}

type named struct {
	Name string `json:"name"`
}

func (c *client) post(doc interface{}) (*http.Response, error) {
	buf, err := json.Marshal(doc)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequest("POST", c.url, bytes.NewBuffer(buf))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/vnd.ksql.v1+json; charset=utf-8")
	req.Header.Set("Accept", "application/vnd.ksql.v1+json")
	return http.DefaultClient.Do(req)
}

func (c *client) execute(statement string) error {
	resp, err := c.post(map[string]interface{}{
		"ksql": statement,
		"streamsProperties": map[string]interface{}{
			"ksql.sink.partitions":           "1",
			"ksql.streams.auto.offset.reset": "earliest",
		},
	})
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		data, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			return errors.Errorf("received status code %v", resp.StatusCode)
		}
		return errors.Errorf("received status code %v: %v", resp.StatusCode, string(data))
	}
	var results []map[string]interface{}
	err = json.NewDecoder(resp.Body).Decode(&results)
	if err != nil {
		return err
	}
	if len(results) < 1 {
		return fmt.Errorf("missing result in response")
	}
	log.Printf("execute results: %+v", results)
	return nil
}

func (c *client) describe(name string) (*SourceDescription, error) {
	resp, err := c.post(map[string]interface{}{
		"ksql": fmt.Sprintf("DESCRIBE %v;", name),
	})
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		data, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			return nil, errors.Errorf("received status code %v", resp.StatusCode)
		}
		return nil, errors.Errorf("received status code %v: %v", resp.StatusCode, string(data))
	}
	var descriptions []DescriptionResult
	decoder := json.NewDecoder(resp.Body)
	err = decoder.Decode(&descriptions)
	if err != nil {
		return nil, err
	}
	if len(descriptions) != 1 {
		return nil, errors.Errorf("expected 1 description, got %d", len(descriptions))
	}
	d := descriptions[0].SourceDescription
	return &d, nil
}

func (c *client) list(item string) ([]string, error) {
	resp, err := c.post(map[string]interface{}{
		"ksql": "LIST " + item + ";",
	})
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var results []map[string]interface{}
	err = json.NewDecoder(resp.Body).Decode(&results)
	if err != nil {
		return nil, err
	}
	if len(results) < 1 {
		return nil, fmt.Errorf("missing result in response")
	}
	result := results[0]
	itemType, ok := result["@type"].(string)
	if !ok {
		return nil, fmt.Errorf("missing @type in result")
	}
	var names []string
	listItems := result[itemType].([]interface{})
	for _, listItem := range listItems {
		listItemInfo := listItem.(map[string]interface{})
		name, ok := listItemInfo["name"].(string)
		if ok {
			names = append(names, name)
		} else {
			id, ok := listItemInfo["id"].(string)
			if ok {
				names = append(names, id)
			}
		}
	}
	return names, nil
}

func main() {
	filename := "config.yaml"
	if fn := os.Getenv("KSQL_CONFIG"); fn != "" {
		filename = fn
	}
	data, err := ioutil.ReadFile(filename)
	if err != nil {
		log.Fatalf("failed to read the configuration file: %v", err)
	}
	var config Config
	err = yaml.Unmarshal(data, &config)
	if err != nil {
		log.Fatalf("failed to parse the configuration file: %v", err)
	}

	ksqlAddress := "http://localhost:8088/ksql"
	if addr := os.Getenv("KSQL_SERVER"); addr != "" {
		ksqlAddress = fmt.Sprintf("%v/ksql", addr)
	}
	c := &client{
		url: ksqlAddress,
	}
	streams, err := c.list("STREAMS")
	if err != nil {
		log.Fatalf("failed to list streams: %v")
	}
	sort.Strings(streams)
	tables, err := c.list("TABLES")
	if err != nil {
		log.Fatalf("failed to list tables: %v", err)
	}
	sort.Strings(tables)

	// first we go through the list and see if anything has changed
	// and needs dropping
	for _, entry := range config.Entries {
		entry.Name = strings.ToUpper(entry.Name)
		switch entry.Type {
		case StatementEntry:
		case TableEntry, StreamEntry:
			if !entry.Base {
				checkItem(c, entry.Name, entry.KSQL, streams, tables)
			}
		default:
			log.Fatalf("unknown entry type: %v", entry.Type)
		}
	}

	streams, err = c.list("STREAMS")
	if err != nil {
		log.Fatalf("failed to list streams: %v", err)
	}
	sort.Strings(streams)
	tables, err = c.list("TABLES")
	if err != nil {
		log.Fatalf("failed to list tables: %v", err)
	}
	sort.Strings(tables)

	// now we go through the list and create what needs
	// creating
	for _, entry := range config.Entries {
		e := entry
		switch e.Type {
		case StatementEntry:
			if err := c.execute(e.KSQL); err != nil {
				log.Printf("failed to execute statement %q: %v", e.KSQL, err)
			}
		case TableEntry, StreamEntry:
			if inSortedSlice(streams, e.Name) ||
				inSortedSlice(tables, e.Name) {
				continue
			}
			log.Printf("creating %v", e.Name)
			if err := c.execute(e.KSQL); err != nil {
				log.Printf("failed to create %q: %v", e.Name, err)
			}
		default:
			log.Fatalf("unknown entry type: %v", e.Type)
		}
	}
}

func inSortedSlice(slice []string, item string) bool {
	i := sort.SearchStrings(slice, item)
	if i < len(slice) && slice[i] == item {
		return true
	}
	return false
}

func checkItem(c *client, name, ksql string, existingStreams, existingTables []string) {
	if !inSortedSlice(existingStreams, name) &&
		!inSortedSlice(existingTables, name) {
		// if the item does not exist, we have nothing to do
		return
	}
	description, err := c.describe(name)
	if err != nil {
		log.Fatalf("failed to retrieve description: %v", err)
	}
	if len(description.WriteQueries) != 1 {
		log.Fatalf("no write queries found for %v: %+v", name, description)
	}
	// if the write query is different, we need to drop the item
	// and all items that depend on it
	if description.WriteQueries[0].QueryString != ksql {
		log.Fatalf("query string for %q has changed: %v VS %v",
			name,
			ksql,
			description.WriteQueries[0].QueryString,
		)
	}
	return
}
